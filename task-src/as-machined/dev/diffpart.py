import sys
sys.path.insert(0, '/w/tests')
import check_models as cm, cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
T = cm.read_step(sys.argv[2]); A = cm.read_step(sys.argv[1])
tb = cm.bbox(T); best = None
for m in cm.rotations():
    R = cm.transformed(A, m, (0, 0, 0)); rb = cm.bbox(R)
    if max(abs((rb[3+i]-rb[i]) - (tb[3+i]-tb[i])) for i in range(3)) > 0.05: continue
    P = cm.transformed(A, m, tuple(tb[i]-rb[i] for i in range(3)))
    x = cm.volume(BRepAlgoAPI_Cut(P, T).Shape()) + cm.volume(BRepAlgoAPI_Cut(T, P).Shape())
    if best is None or x < best[0]: best = (x, P)
P = best[1]
for name, sh in (("agent has extra (truth removed)", BRepAlgoAPI_Cut(P, T).Shape()), ("truth has extra", BRepAlgoAPI_Cut(T, P).Shape())):
    s = cq.Shape.cast(sh)
    for so in s.Solids():
        if so.Volume() < 0.01: continue
        b = so.BoundingBox()
        o = (-612, -268, -455)
        print(name, round(so.Volume(), 3), [round(v, 3) for v in (b.xmin-o[0], b.ymin-o[1], b.zmin-o[2], b.xmax-o[0], b.ymax-o[1], b.zmax-o[2])])
