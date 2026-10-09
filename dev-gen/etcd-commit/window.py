import sys, json, glob, base64
from walparse import dump
from mvcc import Store
d = sys.argv[1]
hs4, e4 = dump(f"{d}/members/m4/data"); hs2, e2 = dump(f"{d}/members/m2/data")
s = Store(); rev4 = {}
for e in e4:
    if e["req"]: s.apply(e["req"])
    rev4[e["index"]] = s.rev
print("m4 commit", hs4["commit"], "last", e4[-1]["index"], "rev at last", s.rev, "| m2 commit", hs2["commit"], "last", e2[-1]["index"])
s2 = Store()
for e in e2:
    if e["req"]: s2.apply(e["req"])
    if e["index"] > e4[-1]["index"] - 3: print("m2", e["index"], e["term"], s2.rev, e["raw"][:150])
recs = []
for f in glob.glob(f"{d}/logs/*.jsonl"):
    recs += [json.loads(l) for l in open(f)]
recs.sort(key=lambda r: r["ts"])
last = recs[-80:]
errs = [r for r in recs if "error" in r]
print("errors total", len(errs))
import collections
print(collections.Counter((r["ts"][:19], r["error"][:40]) for r in errs).most_common(30))
hi = [r for r in recs if "resp" in r and int(r["resp"].get("header", {}).get("revision", 0)) > s.rev]
print("responses with revision beyond m4:", [(r["ts"], r["call"], r["resp"]["header"]["revision"]) for r in hi])
