"""how many keys change when the reverse ordering rule for open calls is dropped. usage: tailscan.py RUN..."""
import sys, json, multiprocessing as mp
from quorum import analyze
def run(r, q):
    try:
        d = json.load(open(f"{r}/screen.json")); drop = tuple(map(tuple, d["drop"]))
        a = (f"{r}/members/m4/data", f"{r}/members/m5/data", f"{r}/logs")
        A = analyze(*a, drop=drop); B = analyze(*a, drop=drop, lin_tail=False)
        ka, kb = A["present"], B["present"]; ua, ub = set(A["uncertain"]), set(B["uncertain"])
        wrong = {k for k in set(ka) | set(kb) if ka.get(k) != kb.get(k)} | (ua ^ ub)
        q.put((r, d["load"], len(ka), len(ua), len(wrong), len(ub - ua)))
    except Exception as e:
        q.put((r, "err", str(e)[:60]))
for r in sys.argv[1:]:
    q = mp.Queue(); p = mp.Process(target=run, args=(r, q)); p.start(); p.join(240)
    if p.is_alive(): p.kill(); print(r, "timeout", flush=True); continue
    print(*q.get(), flush=True)
