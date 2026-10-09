import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demand, sumolib
net = sumolib.net.readNet(sys.argv[1])
term = len(sys.argv) < 3 or sys.argv[2] != "half"
mov = {}
for a, b, v, prof in demand.streams(term):
    pk = v * (1.0 if prof is demand.commute_profile else 1.0)
    path, _ = net.getShortestPath(net.getEdge(a), net.getEdge(b))
    ids = [e.getID() for e in path]
    for x, y in zip(ids, ids[1:]):
        j = net.getEdge(x).getToNode().getID()
        mov[(j, x, y)] = mov.get((j, x, y), 0) + pk
for k in sorted(mov):
    print(k, round(mov[k]))
appr = {}
for (j, x, y), v in mov.items():
    appr[(j, x)] = appr.get((j, x), 0) + v
print()
for k in sorted(appr):
    print(k, round(appr[k]))
