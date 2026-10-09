"""evidence only analysis for the tarn-kv outage.

evidence only: m4 + m5 data dirs and the service call logs. every history consistent with that
evidence is enumerated; a key is determined iff all of them agree on its final value.
the real history (m2's log) is used only to assert that it is one of the enumerated ones.

"""
import sys, json, glob, base64, itertools
from walparse import dump
from mvcc import Store, one

ABSENT = None

def b(x): return base64.b64decode(x) if x is not None else None

# ---------- canonical request signatures
def sig_cmp_entry(c):
    t = one(c, "target", "VERSION"); r = one(c, "result", "EQUAL")
    t = t if isinstance(t, str) else ["VERSION", "CREATE", "MOD", "VALUE", "LEASE"][t]
    r = r if isinstance(r, str) else ["EQUAL", "GREATER", "LESS", "NOT_EQUAL"][r]
    v = {"VERSION": one(c, "version", 0), "CREATE": one(c, "create_revision", 0), "MOD": one(c, "mod_revision", 0),
         "VALUE": one(c, "value", b""), "LEASE": one(c, "lease", 0)}[t]
    return (t, r, one(c, "key"), one(c, "range_end"), v)

def sig_op_entry(op):
    if "request_put" in op:
        p = op["request_put"][0]; return ("put", one(p, "key"), one(p, "value", b""), one(p, "lease", 0))
    d = op["request_delete_range"][0]; return ("del", one(d, "key"), one(d, "range_end"))

def sig_entry(req):
    if "put" in req:
        p = req["put"][0]; return ("put", one(p, "key"), one(p, "value", b""), one(p, "lease", 0))
    if "txn" in req:
        t = req["txn"][0]
        return ("txn", tuple(sig_cmp_entry(c) for c in t.get("compare", [])),
                tuple(sig_op_entry(o) for o in t.get("success", [])), tuple(sig_op_entry(o) for o in t.get("failure", [])))
    if "delete_range" in req:
        d = req["delete_range"][0]; return ("del", one(d, "key"), one(d, "range_end"))
    return None

def sig_cmp_log(c):
    t = c.get("target", "VERSION"); r = c.get("result", "EQUAL")
    v = {"VERSION": int(c.get("version", 0)), "CREATE": int(c.get("create_revision", 0)), "MOD": int(c.get("mod_revision", 0)),
         "VALUE": b(c.get("value", "")), "LEASE": int(c.get("lease", 0))}[t]
    return (t, r, b(c["key"]), b(c.get("range_end")), v)

def sig_op_log(op):
    if "request_put" in op:
        p = op["request_put"]; return ("put", b(p["key"]), b(p.get("value", "")), int(p.get("lease", 0)))
    d = op["request_delete_range"]; return ("del", b(d["key"]), b(d.get("range_end")))

def sig_log(call, req):
    if call == "/v3/kv/put": return ("put", b(req["key"]), b(req.get("value", "")), int(req.get("lease", 0)))
    if call == "/v3/kv/txn":
        return ("txn", tuple(sig_cmp_log(c) for c in req.get("compare", [])),
                tuple(sig_op_log(o) for o in req.get("success", [])), tuple(sig_op_log(o) for o in req.get("failure", [])))
    if call == "/v3/kv/deleterange": return ("del", b(req["key"]), b(req.get("range_end")))
    return None

def req_from_sig(s):
    """rebuild an apply()-able request dict from a signature (for logged calls not in any wal)."""
    def op(o):
        if o[0] == "put":
            d = {"key": [o[1]], "value": [o[2]]}
            if o[3]: d["lease"] = [o[3]]
            return {"request_put": [d]}
        d = {"key": [o[1]]}
        if o[2] is not None: d["range_end"] = [o[2]]
        return {"request_delete_range": [d]}
    if s[0] == "put": return op(s)["request_put"] and {"put": op(s)["request_put"]}
    if s[0] == "del": return {"delete_range": op(s)["request_delete_range"]}
    cmps = []
    for t, r, k, e, v in s[1]:
        c = {"target": [t], "result": [r], "key": [k]}
        if e is not None: c["range_end"] = [e]
        c[{"VERSION": "version", "CREATE": "create_revision", "MOD": "mod_revision", "VALUE": "value", "LEASE": "lease"}[t]] = [v]
        cmps.append(c)
    return {"txn": [{"compare": cmps, "success": [op(o) for o in s[2]], "failure": [op(o) for o in s[3]]}]}

def footprint(s):
    keys = set()
    def add(k, e):
        keys.add((k, e))
    if s[0] in ("put", "del"): add(s[1], s[2] if s[0] == "del" else None)
    else:
        for c in s[1]: add(c[2], c[3])
        for o in s[2] + s[3]: add(o[1], o[2] if o[0] == "del" else None)
    return keys

# ---------- evidence
DEFAULTS = {"term": True, "lin": True, "quorum_cut": True, "dead_member": False, "reads": True, "watch": True,
            "hardstate_only": False, "lin_tail": True, "drop": ()}

def analyze(m4, m5, calls_dir, **opts):
    o = dict(DEFAULTS, **opts)
    drop = set(o["drop"])
    hs4, P = dump(m4)
    hs5, E5 = dump(m5)
    pidx = {e["index"]: e for e in P}
    L = P[-1]["index"]
    D = None
    for e in E5:
        p = pidx.get(e["index"])
        if p is None or p["term"] != e["term"]:
            D = e["index"]; break
    # m5's commit is on its own log; it only counts where m5 agrees with m4
    C0 = max(hs4["commit"], hs5["commit"] if D is None or hs5["commit"] < D else 0)
    assert D is not None and C0 >= D, (D, C0)  # m4's committed prefix overruns the divergence: m5's tail is dead
    dead_sigs = {sig_entry(e["req"]) for e in E5 if e["index"] >= D and e["req"]}

    ent_of = {}  # signature -> index in P
    for e in P:
        if e["req"]:
            s = sig_entry(e["req"])
            if s is not None:
                assert s not in ent_of, ("duplicate request in wal", s)
                ent_of[s] = e["index"]

    calls = []
    for f in sorted(glob.glob(f"{calls_dir}/*.jsonl")):
        for line in open(f):
            calls.append(json.loads(line))
    calls.sort(key=lambda r: r["ts"])
    calls = [r for r in calls if (r.get("svc"), r.get("sent")) not in drop]

    writes = []   # every logged write call
    reads = []    # (R, key, end, count_only, kvs/count)
    watches = []  # streams
    stream = None
    watch_seen = []  # (time logged, highest revision delivered)
    for r in calls:
        if r["call"] in ("/v3/kv/put", "/v3/kv/txn", "/v3/kv/deleterange"):
            s = sig_log(r["call"], r["req"])
            w = {"sig": s, "sent": r["sent"], "ts": r["ts"], "svc": r["svc"],
                 "member": r["endpoint"].split("//")[1].split(":")[0]}
            if "resp" in r:
                w["status"] = "ok"; w["rev"] = int(r["resp"]["header"]["revision"]); w["term"] = int(r["resp"]["header"]["raft_term"])
                w["succeeded"] = r["resp"].get("succeeded", False) if r["call"] == "/v3/kv/txn" else None
            elif "Connection refused" in r["error"]:
                w["status"] = "refused"
            else:
                w["status"] = "unknown"
            writes.append(w)
        elif r["call"] == "/v3/kv/range" and "resp" in r:
            q = r["req"]; R = int(r["resp"]["header"]["revision"]); RT = int(r["resp"]["header"]["raft_term"])
            if q.get("count_only"):
                reads.append({"R": R, "T": RT, "ts": r["ts"], "key": b(q["key"]), "end": b(q.get("range_end")), "count": int(r["resp"].get("count", 0))})
            else:
                kvs = {b(kv["key"]): (b(kv.get("value", "")), int(kv["mod_revision"]), int(kv["version"]), int(kv["create_revision"]))
                       for kv in r["resp"].get("kvs", [])}
                reads.append({"R": R, "T": RT, "ts": r["ts"], "key": b(q["key"]), "end": b(q.get("range_end")), "kvs": kvs})
        elif r["call"] == "/v3/watch":
            res = r["stream"].get("result", {})
            if res.get("created"):
                stream = {"R0": int(res["header"]["revision"]), "events": [], "bounds": []}; watches.append(stream)
            elif stream is not None:
                if res.get("events"):
                    stream["bounds"].append((max(int(ev["kv"]["mod_revision"]) for ev in res["events"]), int(res["header"]["raft_term"])))
                for ev in res.get("events", []):
                    kv = ev["kv"]
                    stream["events"].append((int(kv["mod_revision"]), b(kv["key"]), ev.get("type", "PUT"),
                                             b(kv.get("value", "")) if ev.get("type", "PUT") == "PUT" else None))
    assert len({w["sig"] for w in writes}) == len(writes), "logged writes are not unique"
    for w in writes:
        assert w["sig"] is not None

    from datetime import datetime as _dt
    def _t(x): return _dt.strptime(x, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
    # quorum loss. m5 never acked an entry of m4's last term (its log stops in an older term), so commits in that
    # term need three of m1..m4. a refused or dropped connection proves that member's process was gone by then.
    dead_at = {}
    for r in calls:
        if "error" in r and any(x in r["error"] for x in ("Connection refused", "Connection reset", "closed connection")):
            m = r["endpoint"].split("//")[1].split(":")[0]
            dead_at[m] = min(dead_at.get(m, float("inf")), _t(r["ts"]))
    pool = sorted(dead_at.get(m, float("inf")) for m in ("m1", "m2", "m3", "m4"))
    T_quorum_lost = pool[1]  # second death among the four leaves fewer than three
    for w in writes:
        w["after_quorum"] = o["quorum_cut"] and _t(w["sent"]) >= T_quorum_lost
        if o["dead_member"] and _t(w["ts"]) > dead_at.get(w["member"], float("inf")):
            # a member that is gone cannot hand a call to the leader any more
            w["ts"] = _dt.utcfromtimestamp(dead_at[w["member"]]).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    # linearizability, both ways. anything observed (ack, read, watch delivery) before a call was sent is at a
    # lower revision than that call if it commits; an acked write sent after a call ended is at a higher one.
    from datetime import datetime as _dt
    def _t(x): return _dt.strptime(x, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
    done_obs = sorted([( _t(w["ts"]), w["rev"]) for w in writes if w["status"] == "ok"] +
                      [(_t(q["ts"]), q["R"]) for q in reads] + [(_t(a), r_) for a, r_ in watch_seen])
    acked_by_sent = sorted((_t(w["sent"]), w["rev"]) for w in writes if w["status"] == "ok")
    import bisect
    _done_t = [x[0] for x in done_obs]
    _pref = []; m_ = 0
    for _, r_ in done_obs: m_ = max(m_, r_); _pref.append(m_)
    _sent_t = [x[0] for x in acked_by_sent]
    _suf = [0] * len(acked_by_sent); m_ = float("inf")
    for i in range(len(acked_by_sent) - 1, -1, -1): m_ = min(m_, acked_by_sent[i][1]); _suf[i] = m_
    for w in writes:
        i = bisect.bisect_left(_done_t, _t(w["sent"]))
        w["rev_lo"] = _pref[i - 1] if i > 0 else 0          # its revision must be above this
        j = bisect.bisect_right(_sent_t, _t(w["ts"]))
        w["rev_hi"] = _suf[j] if j < len(_suf) else float("inf")  # and below this

    # observation lookup by revision
    obs_at = {}
    for q in reads: obs_at.setdefault(q["R"], []).append(("read", q))
    watch_changes = {}  # revision -> list of (key, type, value) seen by a complete stream
    watch_spans = []
    for st in watches:
        if st["events"]:
            hi = max(e[0] for e in st["events"])
            watch_spans.append((st["R0"], hi, st))
            for rev, k, typ, v in st["events"]:
                watch_changes.setdefault(rev, []).append((k, typ, v))
    WATCH_PREFIX = (b"/config/", b"/config0")

    def in_range(k, key, end):
        if end is None: return k == key
        return key <= k < end

    def check_read(store, q):
        ks = [k for k in store.kv if in_range(k, q["key"], q["end"])]
        if "count" in q: return len(ks) == q["count"]
        got = {k: (store.kv[k]["value"], store.kv[k]["mod"], store.kv[k]["version"], store.kv[k]["create"]) for k in ks}
        return got == q["kvs"]

    def check_watch(rev, written, before, store):
        """written: keys changed at this revision. complete streams covering rev must show exactly the /config/ changes."""
        cfg = sorted(k for k in written if in_range(k, *WATCH_PREFIX))
        covering = [st for lo, hi, st in watch_spans if lo < rev <= hi]
        if not covering: return True
        seen = {}
        for k, typ, v in watch_changes.get(rev, []): seen[k] = (typ, v)
        want = {}
        for k in cfg:
            want[k] = ("PUT", store.kv[k]["value"]) if k in store.kv else ("DELETE", None)
        return want == seen

    def apply_checked(store, req, rev_expect=None, succ_expect=None):
        before_rev = store.rev
        written = store.apply(req)
        if rev_expect is not None and store.rev != rev_expect: return False
        if succ_expect is not None and getattr(store, "last_txn_ok", None) != succ_expect: return False
        if store.rev != before_rev:
            for kind, q in obs_at.get(store.rev, []):
                if o["reads"] and not check_read(store, q): return False
            if o["watch"] and not check_watch(store.rev, written, None, store): return False
        return True

    # ---------- replay the fixed prefix P[..C0], checking every observation that lands there
    acked = {w["sig"]: w for w in writes if w["status"] == "ok"}
    base = Store()
    for e in P:
        if e["index"] > C0: break
        if e["req"]:
            s = sig_entry(e["req"]); w = acked.get(s)
            ok = apply_checked(base, e["req"], w["rev"] if w else None, w["succeeded"] if w and s[0] == "txn" else None)
            assert ok, ("observation contradicts the committed prefix", e["index"])
    rev_C0 = base.rev
    maxR = max([w["rev"] for w in writes if w["status"] == "ok"] + [q["R"] for q in reads] +
               [hi for lo, hi, st in watch_spans])

    from datetime import datetime
    def t(x): return datetime.strptime(x, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()

    worlds = []   # (c, S0 list of sigs, state after S0, free pool)
    TERM_PRUNED = []
    for c in range(C0, (C0 if o["hardstate_only"] else L) + 1):
        if c > C0 and not pidx[c]["req"] and False: pass
        st = base.clone(); ok = True
        for i in range(C0 + 1, c + 1):
            e = pidx[i]
            if e["req"]:
                s = sig_entry(e["req"]); w = acked.get(s)
                if not apply_checked(st, e["req"], w["rev"] if w else None, w["succeeded"] if w and s[0] == "txn" else None):
                    ok = False; break
        if not ok: continue
        in_world = {sig_entry(e["req"]) for e in P if e["index"] <= c and e["req"]}
        beyond = {sig_entry(e["req"]) for e in P if e["index"] > c and e["req"]}
        if any(s in beyond for s in acked): continue  # an acked call whose only entry would be uncommitted
        A = [w for w in writes if w["status"] == "ok" and w["sig"] not in in_world]
        committed_acked_in_P = [w for w in writes if w["status"] == "ok" and w["sig"] in in_world]
        latest_sent_in_P = max(t(w["sent"]) for w in committed_acked_in_P)
        U = []
        for w in writes:
            if w["status"] != "unknown": continue
            s = w["sig"]
            if s in in_world or s in beyond or s in dead_sigs or s in ent_of: continue
            if w["after_quorum"]: continue  # sent after the last quorum was gone: never proposed into a commit
            # ended before a committed call (already inside P[..c]) was sent: it would have to sit before it
            if o["lin_tail"] and any(t(w["ts"]) < t(z["sent"]) for z in committed_acked_in_P): continue
            U.append(w)
        # S0 fills revisions rev_c+1 .. maxR, one per call (every logged write bumps exactly once)
        n = maxR - st.rev
        if n < 0: continue
        fixed = {}
        bad = False
        for w in A:
            pos = w["rev"] - st.rev
            if pos < 1 or pos > n or pos in fixed: bad = True; break
            fixed[pos] = w
        if bad: continue
        results = []
        def dfs(pos, store, used, seq):
            if pos > n:
                results.append((list(seq), store.clone(), set(used))); return
            cands = [fixed[pos]] if pos in fixed else [u for u in U if u["sig"] not in used]
            for w in cands:
                # real time: anything that ended before w was sent and is already placed is fine; anything that ended
                # before an already placed call was sent cannot come after it
                if any(t(w["ts"]) < t(p["sent"]) for p in seq if p["status"] == "ok"): continue
                r_w = store.rev + 1
                if o["lin"] and w["status"] != "ok" and not (w["rev_lo"] < r_w < w["rev_hi"]): continue
                s2 = store.clone()
                if not apply_checked(s2, req_from_sig(w["sig"]), w.get("rev"), w.get("succeeded") if w["sig"][0] == "txn" and w["status"] == "ok" else None):
                    continue
                used.add(w["sig"]); seq.append(w)
                dfs(pos + 1, s2, used, seq)
                seq.pop(); used.discard(w["sig"])
        dfs(1, st, set(), [])
        # raft_term in a response header bounds the term of every entry up to the revision it reports.
        # the entry at c+1 must have a term in [term(P[c]), B]; if that interval is just term(P[c+1]) it would be
        # m4's own entry (one leader per term, log matching), which this world says is not committed.
        term_of = {e["index"]: e["term"] for e in P}
        bounds = [w["term"] for w in A] + [q["T"] for q in reads if q["R"] > st.rev] + \
                 [T for st_ in watches for R_, T in st_["bounds"] if R_ > st.rev]
        if c < L and bounds:
            B = min(bounds); lo = term_of[c]
            if o["term"] and lo == B == term_of[c + 1]:
                if results: TERM_PRUNED.append(c)
                continue
        for seq, s_end, used in results:
            free = [u for u in U if u["sig"] not in used
                    and (not o["lin_tail"] or not any(t(u["ts"]) < t(z["sent"]) for z in seq if z["status"] == "ok"))
                    and (u["rev_hi"] == float("inf") or not o["lin_tail"])]
            worlds.append((c, [w["sig"] for w in seq], s_end, free))

    assert worlds, "no consistent history"

    # ---------- possible final values
    def components(free):
        parent = list(range(len(free)))
        def find(x):
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        fps = [footprint(u["sig"]) for u in free]
        def overlap(a, bb):
            for k1, e1 in a:
                for k2, e2 in bb:
                    if e1 is None and e2 is None:
                        if k1 == k2: return True
                    else:
                        lo1, hi1 = k1, (e1 if e1 is not None else k1 + b"\x00")
                        lo2, hi2 = k2, (e2 if e2 is not None else k2 + b"\x00")
                        if lo1 < hi2 and lo2 < hi1: return True
            return False
        for i in range(len(free)):
            for j in range(i + 1, len(free)):
                if overlap(fps[i], fps[j]): parent[find(i)] = find(j)
        groups = {}
        for i in range(len(free)): groups.setdefault(find(i), []).append(free[i])
        return list(groups.values())

    per_world = []
    max_comp = 0
    for c, seq, s_end, free in worlds:
        pw = {}
        def note(k, v): pw.setdefault(k, set()).add(v)
        comps = components(free)
        touched = set()
        for comp in comps:
            max_comp = max(max_comp, len(comp))
            assert len(comp) <= 6, "component too large to enumerate"
            outcomes = []
            for r_ in range(len(comp) + 1):
                for sub in itertools.permutations(comp, r_):
                    if any(t(sub[j]["ts"]) < t(sub[i]["sent"]) for i in range(len(sub)) for j in range(i + 1, len(sub))):
                        continue  # j ended before i was sent but sits after it
                    s2 = s_end.clone()
                    for w in sub: s2.apply(req_from_sig(w["sig"]))
                    outcomes.append(s2)
            fkeys = set()
            for u in comp:
                for k, e in footprint(u["sig"]):
                    fkeys |= {kk for o in outcomes for kk in o.kv if in_range(kk, k, e)}
                    if e is None: fkeys.add(k)
            for k in fkeys:
                for o in outcomes:
                    note(k, o.kv[k]["value"] if k in o.kv else ABSENT)
            touched |= fkeys
        for k, v in s_end.kv.items():
            if k not in touched: note(k, v["value"])
        per_world.append(pw)
    all_keys = set().union(*[set(pw) for pw in per_world])
    possible = {}
    for pw in per_world:
        for k in all_keys:
            possible.setdefault(k, set()).update(pw.get(k, {ABSENT}))
    determined = {k: next(iter(v)) for k, v in possible.items() if len(v) == 1}
    uncertain = sorted(k for k, v in possible.items() if len(v) > 1)
    present = {k: v for k, v in determined.items() if v is not ABSENT}

    open_calls = set()
    for c, seq, s_end, free in worlds:
        open_calls |= {sg for sg in seq if sg not in acked} | {u["sig"] for u in free}
    callkey = {w["sig"]: (w["svc"], w["sent"]) for w in writes}
    return {"open_calls": {callkey[sg] for sg in open_calls}, "present": present, "determined": determined, "uncertain": uncertain, "worlds": worlds,
            "P": P, "L": L, "C0": C0, "D": D, "E5": E5, "rev_C0": rev_C0, "maxR": maxR, "max_comp": max_comp,
            "acked": acked, "writes": writes, "ent_of": ent_of, "dead_sigs": dead_sigs, "term_pruned": TERM_PRUNED}
