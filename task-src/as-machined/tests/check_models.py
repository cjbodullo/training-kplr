#!/usr/bin/env python3
"""Compare a submitted STEP model with the sealed as-machined solid (OCCT via cadquery-ocp).

A model passes when, for some proper rotation of the 24 axis-aligned ones (no mirroring) and the
translation that lines up the bounding boxes:
  * it is one valid closed solid;
  * |V - V_true| <= 1e-4 * V_true and vol(A xor T) <= 2e-4 * V_true;
  * every sampled point of either surface lies within 0.02 mm of the other solid.
"""
import itertools
import math
import sys

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex, BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Mat, gp_Pnt, gp_Trsf, gp_Vec, gp_XYZ, gp_GTrsf
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_IN, TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

VOL_REL, XOR_REL, DEV = 1e-4, 2e-4, 0.02


class Bad(Exception):
    pass


def read_step(path):
    r = STEPControl_Reader()
    if r.ReadFile(path) != IFSelect_RetDone:
        raise Bad(f"{path}: not a readable STEP file")
    r.TransferRoots()
    shape = r.OneShape()
    solids = []
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        solids.append(TopoDS.Solid_s(ex.Current()))
        ex.Next()
    if len(solids) != 1:
        raise Bad(f"{path}: expected exactly one solid, found {len(solids)}")
    s = solids[0]
    if not BRepCheck_Analyzer(s).IsValid():
        raise Bad(f"{path}: solid is not valid (BRepCheck)")
    return s


def volume(s):
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(s, p)
    return p.Mass()


def bbox(s):
    b = Bnd_Box()
    b.SetGap(0.0)
    BRepBndLib.AddOptimal_s(s, b, False, False)
    return b.Get()


def rotations():
    """the 24 proper rotations that map coordinate axes to coordinate axes"""
    out = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            m = [[0] * 3 for _ in range(3)]
            for r in range(3):
                m[r][perm[r]] = signs[r]
            det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                   - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                   + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
            if det == 1:
                out.append(m)
    return out


def transformed(s, m, t):
    tr = gp_Trsf()
    tr.SetValues(m[0][0], m[0][1], m[0][2], t[0],
                 m[1][0], m[1][1], m[1][2], t[1],
                 m[2][0], m[2][1], m[2][2], t[2])
    return BRepBuilderAPI_Transform(s, tr, True).Shape()


def surface_points(s, n=5):
    pts = []
    ex = TopExp_Explorer(s, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ad = BRepAdaptor_Surface(f)
        u0, u1, v0, v1 = ad.FirstUParameter(), ad.LastUParameter(), ad.FirstVParameter(), ad.LastVParameter()
        from OCP.BRepTopAdaptor import BRepTopAdaptor_FClass2d
        from OCP.gp import gp_Pnt2d
        from OCP.TopAbs import TopAbs_OUT
        cls = BRepTopAdaptor_FClass2d(f, 1e-7)
        for i in range(n):
            for j in range(n):
                u = u0 + (u1 - u0) * (i + 0.5) / n
                v = v0 + (v1 - v0) * (j + 0.5) / n
                if cls.Perform(gp_Pnt2d(u, v)) == TopAbs_OUT:
                    continue
                pts.append(ad.Value(u, v))
        ex.Next()
    return pts


def boundary(shape):
    """the faces of a solid as one compound: distances are then measured to the surface, so a sample
    point lying inside the other solid (extra material removed there) still counts as off-surface"""
    comp = TopoDS_Compound()
    bld = BRep_Builder()
    bld.MakeCompound(comp)
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        bld.Add(comp, ex.Current())
        ex.Next()
    return comp


def max_dev(points, shape):
    worst = 0.0
    skin = boundary(shape)
    for p in points:
        d = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(p).Vertex(), skin)
        d.Perform()
        worst = max(worst, d.Value())
        if worst > 10 * DEV:
            break
    return worst


def compare(model_path, truth_path):
    T = read_step(truth_path)
    A = read_step(model_path)
    vt, va = volume(T), volume(A)
    if not (math.isfinite(va) and math.isfinite(vt)) or vt <= 0 or va <= 0:
        raise Bad(f"volume is not a finite positive number ({va!r} mm3)")
    if abs(va - vt) > VOL_REL * vt:
        raise Bad(f"volume {va:.3f} mm3, the programs leave {vt:.3f} mm3")
    tb = bbox(T)
    tdim = (tb[3] - tb[0], tb[4] - tb[1], tb[5] - tb[2])
    if not all(math.isfinite(x) for x in tb):
        raise Bad("reference bounding box is not finite")
    best = None
    for m in rotations():
        R = transformed(A, m, (0, 0, 0))
        rb = bbox(R)
        rdim = (rb[3] - rb[0], rb[4] - rb[1], rb[5] - rb[2])
        if not all(math.isfinite(x) for x in rb):
            continue
        if max(abs(a - b) for a, b in zip(rdim, tdim)) > 0.05:
            continue
        t = (tb[0] - rb[0], tb[1] - rb[1], tb[2] - rb[2])
        P = transformed(A, m, t)
        x1, x2 = BRepAlgoAPI_Cut(P, T), BRepAlgoAPI_Cut(T, P)
        xor = volume(x1.Shape()) + volume(x2.Shape())
        if not math.isfinite(xor):
            continue
        if best is None or xor < best[0]:
            best = (xor, P)
    if best is None:
        raise Bad("overall size does not match the machined part in any orientation")
    xor, P = best
    if xor > XOR_REL * vt:
        raise Bad(f"geometry differs from the machined part (non-overlapping volume {xor:.2f} mm3)")
    d1 = max_dev(surface_points(T), P)
    d2 = max_dev(surface_points(P), T)
    if not (math.isfinite(d1) and math.isfinite(d2)):
        raise Bad("surface deviation is not finite")
    if max(d1, d2) > DEV:
        raise Bad(f"surface deviates from the machined part by {max(d1, d2):.3f} mm")
    return f"V={va:.2f} xor={xor:.4f} dev={max(d1, d2):.5f}"


if __name__ == "__main__":
    try:
        print("PASS", compare(sys.argv[1], sys.argv[2]))
    except Bad as e:
        print("FAIL", e)
        sys.exit(1)
