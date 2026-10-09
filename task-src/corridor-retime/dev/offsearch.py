"""coarse offset search for a given cycle: score = blocking back seconds + big penalty on depart delay."""
import json, os, sys, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demand, design, evalplan, sumolib
evalplan.prep()
net = sumolib.net.readNet(os.path.join(evalplan.BASE, "corridor.net.xml"))
movs = {}
for a, b, v, prof in demand.streams(True):
    path, _ = net.getShortestPath(net.getEdge(a), net.getEdge(b))
    ids = [e.getID() for e in path]
    for x, y in zip(ids, ids[1:]):
        movs.setdefault((net.getEdge(x).getToNode().getID(), x), {}).setdefault(y, 0)
        movs[(net.getEdge(x).getToNode().getID(), x)][y] += v
C = int(sys.argv[1]); seeds = [int(x) for x in sys.argv[2].split(",")]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 20
best = []
for o2 in range(0, C, step):
    for o3 in range(0, C, step):
        for o4 in [o3 - 10, o3, o3 + 10]:
            offs = {"J1": 0, "J2": o2, "J3": o3, "J4": o4 % C}
            plan = design.design(movs, C, offs)
            res = evalplan.evaluate(plan, seeds, tag=f"o{o2}_{o3}_{o4}")
            sc = sum(sum(m["bb_seconds"].values()) + 10 * m["depart_delay_max"] + 1000 * m["teleports"] for m in res.values())
            best.append((sc, offs))
            print(sc, offs, flush=True)
best.sort(key=lambda x: x[0])
print("BEST", best[:5])
