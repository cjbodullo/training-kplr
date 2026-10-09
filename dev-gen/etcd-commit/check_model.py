import sys, json, re, subprocess, base64, glob
from walparse import dump
from mvcc import Store, one
d = sys.argv[1]
hs, ents = dump(f"{d}/members/m4/data")
meta = subprocess.run(["etcd-dump-db","iterate-bucket",f"{d}/members/m4/data","meta","--decode"],capture_output=True,text=True).stdout
ci = int.from_bytes(eval("b"+re.search(r'key="consistent_index", value="(.*)"', meta).group(1).join('""')), "big")
print("hs", hs, "consistent_index", ci, "last", ents[-1]["index"])
s = Store(); revat = {}
for e in ents:
    if e["index"] > ci: break
    if e["req"]:
        w = s.apply(e["req"]); revat[e["index"]] = s.rev
raw = subprocess.run(["etcd-dump-db","iterate-bucket",f"{d}/members/m4/data","key","--decode"],capture_output=True,text=True).stdout
print(raw.splitlines()[:3]); print([l for l in raw.splitlines() if "tomb" in l.lower() or "value=[]" in l][:3])
R = re.compile(r'rev=\{main:(\d+) sub:(\d+)\}, value=\[key "(.*)" \| val "(.*)" \| created (\d+) \| mod (\d+) \| ver (\d+)\]')
latest = {}
odd = []
for l in raw.splitlines():
    m = R.match(l)
    if not m: odd.append(l); continue
    main, sub, k, v, cr, mod, ver = m.groups()
    key = (int(main), int(sub))
    if k not in latest or key > latest[k][0]: latest[k] = (key, v, int(cr), int(mod), int(ver))
print("odd", odd[:3], len(odd))
db = {k.encode(): x for k, x in latest.items() if x[4] > 0}
mine = {k: x for k, x in s.kv.items()}
bad = [k for k in set(db) | set(mine) if (k in db) != (k in mine) or (db[k][1].encode(), db[k][3], db[k][4], db[k][2]) != (mine[k]["value"], mine[k]["mod"], mine[k]["version"], mine[k]["create"])]
print("keys db", len(db), "mine", len(mine), "mismatch", len(bad), bad[:5])
print("rev mine", s.rev, "db max", max(x[0][0] for x in latest.values()))
# ack revisions vs replay of the full m4 log
s2 = Store(); byval = {}
for e in ents:
    if e["req"]:
        w = s2.apply(e["req"])
        byval[e["raw"].split("> ",1)[1]] = (e["index"], s2.rev, bool(w))
ok = badack = 0
for f in glob.glob(f"{d}/logs/*.jsonl"):
    for line in open(f):
        r = json.loads(line)
        if r.get("call") == "/v3/kv/put" and "resp" in r:
            v = base64.b64decode(r["req"]["value"]).decode()
            hit = [x for kk, x in byval.items() if f'value:"{v}"' in kk and kk.startswith("put:")]
            if hit:
                ok += hit[0][1] == int(r["resp"]["header"]["revision"])
                badack += hit[0][1] != int(r["resp"]["header"]["revision"])
print("put acks matching revision", ok, "mismatch", badack)
for f in glob.glob(f"{d}/logs/*.jsonl"):
    for line in open(f):
        r = json.loads(line)
        if r.get("call") == "/v3/kv/put" and "resp" in r:
            v = base64.b64decode(r["req"]["value"]).decode()
            hit = [x for kk, x in byval.items() if f'value:"{v}"' in kk and kk.startswith("put:")]
            if hit and hit[0][1] != int(r["resp"]["header"]["revision"]):
                print(r["ts"], r["svc"], v, "log idx/rev", hit[0], "ack", r["resp"]["header"]["revision"], "lease" in r["req"])
