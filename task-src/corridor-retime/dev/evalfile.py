import os, sys, json
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evalplan
pf = os.path.abspath(sys.argv[1]); seeds = [int(x) for x in sys.argv[2].split(",")]
tag = os.path.basename(pf).split(".")[0]
evalplan.prep()
for s in seeds:
    evalplan.day_routes(s, True)
with Pool(7) as p:
    res = dict(p.map(evalplan.one, [(tag, pf, s, True) for s in seeds]))
print(evalplan.summarize(res))
json.dump({s: {k: v for k, v in m.items() if k != "waits"} for s, m in res.items()}, open(f"/dev2/res_{tag}.json", "w"))
