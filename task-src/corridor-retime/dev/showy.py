import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design, evalplan, offdesc, sumolib
evalplan.prep(); net = sumolib.net.readNet(os.path.join(evalplan.BASE, "corridor.net.xml"))
ys = design.stage_y(offdesc.true_movs(net, len(sys.argv) < 2))
print({j: [round(v, 3) for v in y] + [round(sum(y), 3)] for j, y in ys.items()})
