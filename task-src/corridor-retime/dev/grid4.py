import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design, evalplan, offdesc, sumolib
evalplan.prep(); net = sumolib.net.readNet(os.path.join(evalplan.BASE, "corridor.net.xml"))
movs = offdesc.true_movs(net)
C = 120; seeds = [1, 2, 7, 4]
for m in [0, 3, 6]:
    for o4 in [-4, 0, 4]:
        plan = design.design(movs, C, {"J1": 0, "J2": 112, "J3": 0, "J4": o4}, j4_match=m)
        res = evalplan.evaluate(plan, seeds, tag=f"g{m}_{o4}")
        tot = {s: sum(r["bb_seconds"].values()) for s, r in res.items()}
        print(m, o4, offdesc.score(res), tot, json.dumps(plan["J4"]), flush=True)
