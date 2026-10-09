import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design, evalplan, offdesc, sumolib
evalplan.prep(); net = sumolib.net.readNet(os.path.join(evalplan.BASE, "corridor.net.xml"))
movs = offdesc.true_movs(net)
C = int(sys.argv[1]); offs = json.loads(sys.argv[2]); m = int(sys.argv[3]); seeds = [int(x) for x in sys.argv[4].split(",")]
plan = design.design(movs, C, offs, j4_match=m)
print(json.dumps(plan))
res = evalplan.evaluate(plan, seeds, tag="td")
out = [(int(r["depart_delay_max"]), max(r["bb_seconds"].values(), default=0)) for s, r in sorted(res.items())]
for s_, r in sorted(res.items()):
    worst = sorted(r["dd_by"].items(), key=lambda kv: -kv[1])[:2]
    print(s_, [(k, int(v)) for k, v in worst], r["bb_seconds"])
print("fail", sum(1 for dd, bb in out if dd > 180 or bb > 120), "/", len(out), out)
