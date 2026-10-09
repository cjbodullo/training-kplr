import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demand, design, evalplan, sumolib
evalplan.prep()
net = sumolib.net.readNet(os.path.join(evalplan.BASE, "corridor.net.xml"))
movs = {}
for a, b, v, prof in demand.streams(True):
    path, _ = net.getShortestPath(net.getEdge(a), net.getEdge(b))
    ids = [e.getID() for e in path]
    for x, y in zip(ids, ids[1:]):
        j = net.getEdge(x).getToNode().getID()
        movs.setdefault((j, x), {}).setdefault(y, 0)
        movs[(j, x)][y] += v
print(json.dumps(design.stage_y(movs)))
C = int(sys.argv[1]); offs = json.loads(sys.argv[2]); seeds = [int(x) for x in sys.argv[3].split(",")]
plan = design.design(movs, C, offs)
print(json.dumps(plan))
print(evalplan.summarize(evalplan.evaluate(plan, seeds, tag=f"c{C}")))
