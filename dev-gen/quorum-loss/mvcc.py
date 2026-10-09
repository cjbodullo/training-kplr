"""small model of etcd 3.5 mvcc apply semantics for the request kinds tarn-kv uses.

state: key -> dict(value, create, mod, version, lease); rev = current main revision.
apply(req) returns (bumped, info) and mutates the store.
"""
import copy

TARGET = {0: "VERSION", 1: "CREATE", 2: "MOD", 3: "VALUE", 4: "LEASE"}
RESULT = {0: "EQUAL", 1: "GREATER", 2: "LESS", 3: "NOT_EQUAL"}

def one(d, k, default=None):
    v = d.get(k)
    return v[0] if v else default

def norm_enum(v, table):
    if v is None: return table[0]
    if isinstance(v, int): return table[v]
    return v.decode() if isinstance(v, bytes) else v

class Store:
    def __init__(self):
        self.kv = {}; self.rev = 1; self.leases = {}  # lease id -> set(keys)
    def clone(self):
        s = Store(); s.kv = copy.deepcopy(self.kv); s.rev = self.rev
        s.leases = {k: set(v) for k, v in self.leases.items()}; return s

    def _range(self, key, end):
        if end is None: return [key] if key in self.kv else []
        if end == b"\x00": return sorted(k for k in self.kv if k >= key)
        return sorted(k for k in self.kv if key <= k < end)

    def _cmp(self, c):
        key = one(c, "key"); end = one(c, "range_end")
        target = norm_enum(one(c, "target"), TARGET); result = norm_enum(one(c, "result"), RESULT)
        keys = self._range(key, end) if end else [key]
        def val(k):
            kv = self.kv.get(k)
            if target == "VERSION": return kv["version"] if kv else 0
            if target == "CREATE": return kv["create"] if kv else 0
            if target == "MOD": return kv["mod"] if kv else 0
            if target == "VALUE": return kv["value"] if kv else None
            if target == "LEASE": return kv["lease"] if kv else 0
        want = {"VERSION": one(c, "version", 0), "CREATE": one(c, "create_revision", 0),
                "MOD": one(c, "mod_revision", 0), "VALUE": one(c, "value", b""), "LEASE": one(c, "lease", 0)}[target]
        for k in keys:
            v = val(k)
            if target == "VALUE" and v is None: return False  # missing key never matches a value compare
            ok = {"EQUAL": v == want, "NOT_EQUAL": v != want, "GREATER": v > want, "LESS": v < want}[result]
            if not ok: return False
        return True

    def _put(self, p, rev, sub):
        key = one(p, "key"); value = one(p, "value", b""); lease = one(p, "lease", 0)
        old = self.kv.get(key)
        if old and old["lease"]:
            self.leases.get(old["lease"], set()).discard(key)
        if old: ent = {"value": value, "create": old["create"], "mod": rev, "version": old["version"] + 1, "lease": lease}
        else: ent = {"value": value, "create": rev, "mod": rev, "version": 1, "lease": lease}
        self.kv[key] = ent
        if lease: self.leases.setdefault(lease, set()).add(key)

    def _del(self, key, end):
        ks = self._range(key, end)
        for k in ks:
            old = self.kv.pop(k)
            if old["lease"]: self.leases.get(old["lease"], set()).discard(k)
        return ks

    def apply(self, req):
        """req: parsed InternalRaftRequest dict. returns list of written keys (empty = no revision bump)."""
        nrev = self.rev + 1
        if "put" in req:
            self._put(req["put"][0], nrev, 0); self.rev = nrev; return [one(req["put"][0], "key")]
        if "delete_range" in req:
            d = req["delete_range"][0]
            ks = self._del(one(d, "key"), one(d, "range_end"))
            if ks: self.rev = nrev
            return ks
        if "txn" in req:
            t = req["txn"][0]
            ok = all(self._cmp(c) for c in t.get("compare", []))
            ops = t.get("success" if ok else "failure", [])
            written = []
            for op in ops:
                if "request_put" in op:
                    self._put(op["request_put"][0], nrev, 0); written.append(one(op["request_put"][0], "key"))
                elif "request_delete_range" in op:
                    d = op["request_delete_range"][0]
                    written += self._del(one(d, "key"), one(d, "range_end"))
            if written: self.rev = nrev
            self.last_txn_ok = ok
            return written
        if "lease_grant" in req:
            g = req["lease_grant"][0]; self.leases.setdefault(one(g, "ID"), set()); return []
        if "lease_revoke" in req:
            lid = one(req["lease_revoke"][0], "ID")
            ks = sorted(self.leases.pop(lid, set()))
            for k in ks: self.kv.pop(k, None)
            if ks: self.rev = nrev
            return ks
        return []  # cluster_version_set, alarm, checkpoints, ...
