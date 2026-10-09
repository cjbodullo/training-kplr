import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demand, design, evalplan, offdesc, sumolib
evalplan.prep(); net = sumolib.net.readNet(os.path.join(evalplan.BASE, "corridor.net.xml"))
def movs_with(m):
    old = demand.PHASE2; demand.PHASE2 = m
    os.environ["P2"] = "1"; mv = offdesc.true_movs(net); demand.PHASE2 = old
    return mv
seeds = [int(x) for x in sys.argv[1].split(",")]
V = {"true": movs_with(1.75), "pre": movs_with(1.0), "wk4cap": movs_with(1.3), "mean": movs_with(1.25), "TA": movs_with(1.25)}
mix = dict(movs_with(1.75))
pre = movs_with(1.0)
for k in pre:
    if k[0] in ("J3", "J4"):
        mix[k] = pre[k]
V["noprop"] = mix
offs = {"J1": 0, "J2": 112, "J3": 0, "J4": 0}
os.environ["P2"] = "1"
for name, mv in V.items():
    plan = design.design(mv, 120, offs, j4_match=3)
    res = evalplan.evaluate(plan, seeds, tag="ab_" + name)
    out = [(int(r["depart_delay_max"]), max(r["bb_seconds"].values(), default=0)) for s, r in sorted(res.items())]
    fails = sum(1 for dd, bb in out if dd > 180 or bb > 120)
    print(f"{name:7s} greens {[plan[j]['greens'] for j in ['J2','J3','J4']]} fail {fails}/{len(out)} {out}", flush=True)
