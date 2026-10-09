#!/usr/bin/env python3
"""Independent check of the B-rep engine: classify random points analytically (stock box minus
'is this point inside the tool at some position along a feed move') and compare with OCCT's
classification of the exported solid. usage: mc_check.py <models dir> [n]"""
import math
import random
import sys

sys.path.insert(0, "/w/solution")
import fanuc  # noqa: E402
import parts as models  # noqa: E402
import cadquery as cq  # noqa: E402
from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.TopAbs import TopAbs_IN, TopAbs_ON  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402

TL, LEN = models.crib(old_t6=True)       # lot day: the old T6 was in the spindle


def rho(tool, h):
    if h < 0:
        return -1
    R = tool.R
    if tool.kind == "flat":
        return R
    if tool.kind == "bull":
        rc = tool.rc
        if h >= rc:
            return R
        return R - rc + math.sqrt(rc * rc - (rc - h) ** 2)
    hc = (R - tool.r0) / math.tan(math.radians(tool.point / 2))
    return R if h >= hc else tool.r0 + h * math.tan(math.radians(tool.point / 2))


def hdist_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def hdist_arc(p, a, b, c, ccw):
    if not ccw:
        a, b = b, a
    a0 = math.atan2(a[1] - c[1], a[0] - c[0])
    sw = (math.atan2(b[1] - c[1], b[0] - c[0]) - a0) % (2 * math.pi)
    if sw < 1e-9:
        sw = 2 * math.pi
    R = math.hypot(a[0] - c[0], a[1] - c[1])
    ang = (math.atan2(p[1] - c[1], p[0] - c[0]) - a0) % (2 * math.pi)
    if ang <= sw + 1e-12:
        return abs(math.hypot(p[0] - c[0], p[1] - c[1]) - R)
    return min(math.hypot(p[0] - a[0], p[1] - a[1]), math.hypot(p[0] - b[0], p[1] - b[1]))


def removed(p, moves):
    for kind, t, p0, p1, arc in moves:      # rapids cut too (G00 straight line, LRP = 1)
        tool = TL[t]
        zlo = min(p0[2], p1[2])
        r = rho(tool, p[2] - zlo)
        if r < 0:
            continue
        if arc is not None:
            d = hdist_arc(p, p0, p1, arc[0], arc[1])
        else:
            d = hdist_seg(p, p0, p1)
        if d <= r:
            return True
    return False


def main():
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    cnc = "/w/dev/state0918"
    random.seed(7)
    op10, op20 = fanuc.run_part(cnc, [1610, 1620], LEN)
    (b,) = fanuc.run_part(cnc, [1140], LEN)
    (c,) = fanuc.run_part(cnc, [2205], LEN)
    # OP20 placement: recompute from the OP10 solid like models.py, but map points back by hand
    p10 = models.single(models.machine(models.block(124.0, 84.0, 31.0), op10, TL))
    bb = p10.BoundingBox()
    slab = cq.Solid.makeBox(bb.xlen + 20, bb.ylen + 20, 20, cq.Vector(bb.xmin - 10, bb.ymin - 10, bb.zmax - 15))
    wall = p10.intersect(slab).BoundingBox()
    # lot day: OP20 loaded turned over about Y, OP10 right end on the stop, back face on the jaw
    tx, ty, tz = models.STOP_X + wall.xmax, models.JAW_Y - wall.ymax, models.PAR_Z + bb.zmax

    def back(p):       # OP20 frame -> OP10 frame
        return (tx - p[0], p[1] - ty, tz - p[2])

    def in_box(p, dx, dy, dz):
        return (models.STOP_X <= p[0] <= models.STOP_X + dx and models.JAW_Y - dy <= p[1] <= models.JAW_Y
                and models.PAR_Z <= p[2] <= models.PAR_Z + dz)

    cases = {
        "MNF-0610": lambda p: in_box(back(p), 124, 84, 31) and not removed(back(p), op10) and not removed(p, op20),
        "BRG-1140": lambda p: in_box(p, 90, 60, 40) and not removed(p, b),
        "LVR-2205": lambda p: in_box(p, 110, 45, 20) and not removed(p, c),
    }
    regions = {}
    if len(sys.argv) > 3:   # name:x0,y0,z0,x1,y1,z1 in that part's block frame (left/front/bottom)
        for r in sys.argv[3:]:
            nm, v = r.split(":")
            regions.setdefault(nm, []).append([float(x) for x in v.split(",")])
    origin = {"BRG-1140": (models.STOP_X, models.JAW_Y - 60, models.PAR_Z),
              "LVR-2205": (models.STOP_X, models.JAW_Y - 45, models.PAR_Z),
              "MNF-0610": (models.STOP_X, models.JAW_Y - 80, models.PAR_Z)}
    for name, f in cases.items():
        if regions and name not in regions:
            continue
        s = cq.importers.importStep(f"{out}/{name}.step").val()
        bb = s.BoundingBox()
        if name in regions:
            o = origin[name]
            r = regions[name][0]
            bb = type("B", (), dict(xmin=o[0] + r[0], ymin=o[1] + r[1], zmin=o[2] + r[2],
                                    xmax=o[0] + r[3], ymax=o[1] + r[4], zmax=o[2] + r[5]))
        bad = 0
        inside = 0
        for _ in range(n):
            p = (random.uniform(bb.xmin, bb.xmax), random.uniform(bb.ymin, bb.ymax),
                 random.uniform(bb.zmin, bb.zmax))
            cl = BRepClass3d_SolidClassifier(s.wrapped, gp_Pnt(*p), 1e-7)
            st = cl.State()
            if st == TopAbs_ON:
                continue
            occ = st == TopAbs_IN
            ana = f(p)
            inside += occ
            if occ != ana:
                bad += 1
                if bad <= 5:
                    print("  mismatch", name, [round(x, 3) for x in p], "occ", occ, "analytic", ana)
        print(name, "points", n, "inside", inside, "mismatches", bad)


if __name__ == "__main__":
    main()
