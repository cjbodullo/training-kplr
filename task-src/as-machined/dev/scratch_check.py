# dense check in the scratch layer (OP20 machine frame: the scratched face is the top, zmax)
import sys, random
sys.path.insert(0, '/w/dev'); sys.path.insert(0, '/w/solution')
import mc_check as M, cadquery as cq, fanuc
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN, TopAbs_ON
from OCP.gp import gp_Pnt
op10, op20 = fanuc.run_part('/w/dev/state0918', [1610, 1620], M.LEN)
s = cq.importers.importStep('/w/tests/truth/MNF-0610.step').val()
bb = s.BoundingBox()
print('bbox', bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax, flush=True)
random.seed(3); bad = n = removed = 0
for k in range(3000):
    line = random.choice(['v12', 'v68', 'u12', 'u108'])     # OP20 program coords of the drag lines
    if line[0] == 'v':
        x = bb.xmin + random.uniform(10, 110); y = bb.ymin + float(line[1:]) + random.uniform(-0.15, 0.15)
    else:
        x = bb.xmin + float(line[1:]) + random.uniform(-0.15, 0.15); y = bb.ymin + random.uniform(10, 70)
    z = bb.zmax - random.uniform(0, 0.08)
    st = BRepClass3d_SolidClassifier(s.wrapped, gp_Pnt(x, y, z), 1e-7).State()
    if st == TopAbs_ON:
        continue
    n += 1
    occ = st == TopAbs_IN
    ana = not M.removed((x, y, z), op20)
    removed += not occ
    if occ != ana:
        bad += 1
        if bad <= 5:
            print('  mismatch', round(x, 3), round(y, 3), round(z, 4), 'occ', occ, 'analytic', ana)
print('scratch layer points', n, 'removed', removed, 'mismatches', bad)
