"""screen one run: drop knife-edge calls until the answer is the same under every defensible reading of member
death timing, then ablate each rule and record which ones change the answer.
usage: select.py RUNDIR  -> RUNDIR/screen.json"""
import sys, json, multiprocessing as mp
from quorum import analyze

RUN = sys.argv[1]
ARGS = (f"{RUN}/members/m4/data", f"{RUN}/members/m5/data", f"{RUN}/logs")

def answer(A):
    return ({k: v for k, v in A["present"].items()}, tuple(A["uncertain"]))

def run(opts, q):
    try:
        A = analyze(*ARGS, **opts)
        q.put(("ok", answer(A), len(A["worlds"]), sorted(A["open_calls"]),
               sum(1 for c, seq, *_ in A["worlds"] for sg in seq if sg not in A["acked"]), sorted({w[0] for w in A["worlds"]})))
    except Exception as e:
        q.put(("err", f"{type(e).__name__}: {str(e)[:80]}"))

def go(opts, timeout=180):
    q = mp.Queue(); p = mp.Process(target=run, args=(opts, q)); p.start(); p.join(timeout)
    if p.is_alive():
        p.kill(); return ("timeout",)
    return q.get()

drop = set()
for it in range(6):
    res = {name: go(dict(o, drop=tuple(drop))) for name, o in
           {"ref": {}, "dead_member": {"dead_member": True}, "no_quorum_cut": {"quorum_cut": False}}.items()}
    if any(r[0] != "ok" for r in res.values()):
        print(json.dumps({"run": RUN, "fail": {k: v[0:2] if v[0] != "ok" else "ok" for k, v in res.items()}})); sys.exit(0)
    answers = {k: v[1] for k, v in res.items()}
    if len({json.dumps([sorted((a.decode(), b.decode()) for a, b in v[0].items()), [x.decode() for x in v[1]]]) for v in answers.values()}) == 1:
        break
    opens = [set(map(tuple, r[3])) for r in res.values()]
    diff = set.union(*opens) - set.intersection(*opens)
    if not diff:
        print(json.dumps({"run": RUN, "fail": "answers differ but open sets agree"})); sys.exit(0)
    drop |= diff
else:
    print(json.dumps({"run": RUN, "fail": "did not converge"})); sys.exit(0)

ref = res["ref"]
abl = {}
for name, o in {"term": {"term": False}, "lin": {"lin": False}, "reads": {"reads": False},
                "watch": {"watch": False}, "hardstate": {"hardstate_only": True}}.items():
    r = go(dict(o, drop=tuple(drop)))
    abl[name] = "same" if r[0] == "ok" and r[1] == ref[1] else (r[0] if r[0] != "ok" else "changes")
out = {"run": RUN, "drop": sorted(drop), "present": len(ref[1][0]), "uncertain": len(ref[1][1]), "worlds": ref[2],
       "gapfills": ref[4], "c_values": ref[5], "ablation": abl,
       "load": sum(1 for v in abl.values() if v != "same")}
json.dump(out, open(f"{RUN}/screen.json", "w"), indent=1)
print(json.dumps(out))
