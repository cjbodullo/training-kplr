#!/usr/bin/env python3
"""CMM side: measure the inspected characteristics of a solid the way the QC program does
(3-2-1 datum alignment A bottom / B front / C left, then features), and read PC-DMIS text reports.

the solid must be in print orientation: top of the print up, front of the print toward -Y.
"""
import math
import re

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

# characteristic list per part: (name, kind, nominal dict) with print nominals
PLAN = {
    "BRG-1140": [
        ("CIR_DWL1", "hole", dict(X=10.0, Y=30.0, D=6.8)),
        ("CIR_DWL2", "hole", dict(X=80.0, Y=30.0, D=6.8)),
        ("CIR_ROW1", "hole", dict(X=27.5, Y=53.0, D=6.6, DP=10.0)),
        ("CIR_ROW2", "hole", dict(X=42.5, Y=53.0, D=6.6, DP=10.0)),
        ("CIR_ROW3", "hole", dict(X=57.5, Y=53.0, D=6.6, DP=10.0)),
        ("CIR_ROW4", "hole", dict(X=72.5, Y=53.0, D=6.6, DP=10.0)),
        ("PKT_1", "pocket", dict(X=45.0, Y=30.0, L=50.0, W=30.0, DP=12.0)),
        ("SLOT_KEY", "slotx", dict(X=45.0, W=10.0)),
        ("PLN_TOP", "height", dict(Z=40.0)),
    ],
    "LVR-2205": [
        ("CIR_BORE", "hole", dict(X=92.0, Y=22.5, D=20.0)),
        ("CIR_H1", "hole", dict(X=30.0, Y=6.0, D=6.6, DP=12.0)),
        ("CIR_H2", "hole", dict(X=50.0, Y=6.0, D=6.6, DP=12.0)),
        ("CIR_H3", "hole", dict(X=70.0, Y=6.0, D=6.6, DP=12.0)),
        ("CIR_H4", "hole", dict(X=100.0, Y=38.0, D=6.6)),
        ("PKT_KEY", "floor", dict(X=60.0, Y=22.5, DP=8.0)),
        ("PLN_TOP", "height", dict(Z=20.0)),
    ],
    "MNF-0610": [
        ("PLN_TOP", "height", dict(Z=26.0)),
        ("CIR_BC1", "hole", dict(X=100.1244, Y=63.0, D=6.8)),
        ("CIR_BORE_B", "hole_bottom", dict(X=60.0, Y=40.0, D=26.0)),
        ("CIR_T1", "hole", dict(X=12.0, Y=12.0, D=6.6)),
        ("CIR_T2", "hole", dict(X=108.0, Y=12.0, D=6.6)),
        ("CIR_T3", "hole", dict(X=108.0, Y=68.0, D=6.6)),
        ("CIR_T4", "hole", dict(X=12.0, Y=68.0, D=6.6)),
    ],
}
TOL = {"X": 0.05, "Y": 0.05, "D": 0.025, "L": 0.1, "W": 0.1, "DP": 0.05, "Z": 0.05}
SEARCH = 15.0      # the inspector re-teaches a feature found up to this far from nominal


def faces(solid):
    out = []
    for f in solid.Faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        out.append((f, ad))
    return out


def cylinders(solid, zlo=None, zhi=None):
    """vertical cylindrical faces as (x, y, r, zmin, zmax), split faces merged"""
    found = {}
    for f, ad in faces(solid):
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder()
        d = cyl.Axis().Direction()
        if abs(abs(d.Z()) - 1) > 1e-6:
            continue
        loc = cyl.Location()
        bb = f.BoundingBox()
        key = (round(loc.X(), 4), round(loc.Y(), 4), round(cyl.Radius(), 4))
        z0, z1 = found.get(key, (bb.zmin, bb.zmax))
        found[key] = (min(z0, bb.zmin), max(z1, bb.zmax))
    return [(k[0], k[1], k[2], v[0], v[1]) for k, v in found.items()]


def planes(solid, normal):
    """planar faces with the given axis normal, as (coordinate, face bbox)"""
    out = []
    ax = "xyz".index(normal[1])
    for f, ad in faces(solid):
        if ad.GetType() != GeomAbs_Plane:
            continue
        n = f.normalAt()
        v = (n.x, n.y, n.z)[ax]
        if abs(abs(v) - 1) > 1e-6 or (v > 0) != (normal[0] == "+"):
            continue
        bb = f.BoundingBox()
        c = (bb.xmin, bb.ymin, bb.zmin)[ax]
        out.append((c, bb))
    return out


def measure(solid):
    """returns {name: {axis: value}} in the datum frame, for one part in print orientation"""
    bb = solid.BoundingBox()
    o = (bb.xmin, bb.ymin, bb.zmin)
    s = solid.translate(cq.Vector(-o[0], -o[1], -o[2]))
    top = bb.zlen
    return s, top


def inspect(part, solid):
    s, top = measure(solid)
    cyls = cylinders(s)
    res = {}
    for name, kind, nom in PLAN[part]:
        if kind in ("hole", "hole_bottom"):
            best = None
            for x, y, r, z0, z1 in cyls:
                if abs(2 * r - nom["D"]) > 0.6:
                    continue
                if kind == "hole" and z1 < top - 8.0:
                    continue           # not reachable from the top face
                if kind == "hole_bottom" and z0 > 1e-3:
                    continue           # opens on the bottom face
                dist = math.hypot(x - nom["X"], y - nom["Y"])
                if dist <= SEARCH and (best is None or dist < best[0]):
                    best = (dist, x, y, r, z0)
            if best is None:
                res[name] = None
            else:
                res[name] = dict(X=best[1], Y=best[2], D=2 * best[3])
                if "DP" in nom:            # blind hole: depth to the end of full diameter
                    res[name]["DP"] = top - best[4]
        elif kind == "height":
            res[name] = dict(Z=top)
        elif kind == "pocket":
            def wall(normal, near, lo, hi):
                c = [p for p, b in planes(s, normal)
                     if abs(p - near) < 2.0 and b.zmax > top - 1 and b.zmin < top - 3]
                return min(c, key=lambda p: abs(p - near)) if c else None
            xl = wall("+x", nom["X"] - nom["L"] / 2, 0, 0)
            xr = wall("-x", nom["X"] + nom["L"] / 2, 0, 0)
            yf = wall("+y", nom["Y"] - nom["W"] / 2, 0, 0)
            yb = wall("-y", nom["Y"] + nom["W"] / 2, 0, 0)
            fl = [p for p, b in planes(s, "+z") if abs(top - p - nom["DP"]) < 1.0
                  and b.xmin < nom["X"] < b.xmax and b.ymin < nom["Y"] < b.ymax]
            if None in (xl, xr, yf, yb) or not fl:
                res[name] = None
            else:
                res[name] = dict(X=(xl + xr) / 2, Y=(yf + yb) / 2, L=xr - xl, W=yb - yf, DP=top - fl[0])
        elif kind == "slotx":
            xl = [p for p, b in planes(s, "+x") if abs(p - (nom["X"] - nom["W"] / 2)) < 2 and b.ymin < 1]
            xr = [p for p, b in planes(s, "-x") if abs(p - (nom["X"] + nom["W"] / 2)) < 2 and b.ymin < 1]
            res[name] = None if not (xl and xr) else dict(X=(xl[0] + xr[0]) / 2, W=xr[0] - xl[0])
        elif kind == "floor":
            fl = [p for p, b in planes(s, "+z") if abs(top - p - nom["DP"]) < 1.0
                  and b.xmin < nom["X"] < b.xmax and b.ymin < nom["Y"] < b.ymax]
            res[name] = None if not fl else dict(DP=top - fl[0])
    return res


def scratches(solid, depth=0.3):
    """shallow marks in datum A (the bottom face): faces that dip less than `depth` below it.
    returns the runs as (axis, position across, from, to) in the datum frame, merged per line"""
    s, top = measure(solid)
    runs = []
    for f in s.Faces():
        bb = f.BoundingBox()
        if bb.zmax > depth or bb.zlen < 1e-6:
            continue
        if bb.ylen > 3 * bb.xlen:
            runs.append(("Y", round((bb.xmin + bb.xmax) / 2, 1), bb.ymin, bb.ymax))
        elif bb.xlen > 3 * bb.ylen:
            runs.append(("X", round((bb.ymin + bb.ymax) / 2, 1), bb.xmin, bb.xmax))
    merged = {}
    for ax, pos, a, b in runs:
        k = (ax, pos)
        lo, hi = merged.get(k, (a, b))
        merged[k] = (min(lo, a), max(hi, b))
    return sorted((ax, pos, lo, hi) for (ax, pos), (lo, hi) in merged.items())


def scratch_comment(runs):
    if not runs:
        return None
    ys = [r for r in runs if r[0] == "Y"]
    xs = [r for r in runs if r[0] == "X"]
    parts = []
    for ax, pos, lo, hi in ys:
        parts.append(f"ONE RUNS ALONG Y AT ABOUT {pos:.0f} FROM DATUM C")
    if xs:
        parts.append(f"{len(xs)} RUN ALONG X" if len(xs) > 1 else "ONE RUNS ALONG X")
    return ("VISUAL: FINE SCRATCH LINES ON DATUM A FACE, " + ", ".join(parts)
            + ". DEPTH NOT MEASURED. SAME ON ALL SERIALS.")


# ------------------------------------------------------------------------------- reports
def write_report(part, serial, date, res, noise, path, comment=None):
    lines = [
        "PC-DMIS 2023.2 MR1                                   PAGE 1",
        f"PART NAME  : {part}",
        f"REV NUMBER : {'B' if part == 'BRG-1140' else 'A' if part == 'LVR-2205' else 'D'}",
        f"SER NUMBER : {serial}",
        f"STATS COUNT: 1",
        f"DATE={date}  TIME=14:{serial[-2:]}:07  OPERATOR=DMK  MACHINE=GLOBAL S 07.10.07",
        "",
        "A1         =ALIGNMENT/START,RECALL:STARTUP,LIST=YES",
        "              ALIGNMENT/LEVEL,ZPLUS,PLN_A",
        "              ALIGNMENT/ROTATE,XPLUS,TO,LIN_B,ABOUT,ZPLUS",
        "              ALIGNMENT/TRANS,XAXIS,PLN_C",
        "              ALIGNMENT/TRANS,YAXIS,LIN_B",
        "              ALIGNMENT/TRANS,ZAXIS,PLN_A",
        "            ALIGNMENT/END",
        "  (datum A bottom face, B front face, C left end face)",
        "",
    ]
    if comment:
        lines += [f'C1         =COMMENT/REPT,"{comment}"', ""]
    for name, kind, nom in PLAN[part]:
        m = res.get(name)
        lines.append(f"DIM {name}= {'LOCATION' if kind != 'height' else 'DISTANCE'} OF "
                     f"{'CIRCLE' if 'hole' in kind else 'FEATURE'} {name}  UNITS=MM ,$")
        lines.append("GRAPH=OFF  TEXT=OFF  MULT=10.00  OUTPUT=BOTH  HALF ANGLE=NO")
        if m is None:
            lines.append("  *** FEATURE NOT FOUND - NO MEASURED DATA ***")
            lines.append("")
            continue
        lines.append("AX       NOMINAL       +TOL       -TOL       MEAS        DEV     OUTTOL")
        for ax, nv in nom.items():
            if ax not in m:
                continue
            mv = m[ax] + noise()
            dev = mv - nv
            out = max(0.0, abs(dev) - TOL[ax])
            flag = "  ----#" if out > 0 else ""
            lines.append(f"{ax:<4}{nv:11.4f}{TOL[ax]:11.4f}{TOL[ax]:11.4f}{mv:11.4f}{dev:11.4f}{out:11.4f}{flag}")
        lines.append("")
    open(path, "w").write("\n".join(lines) + "\n")


def read_comment(path):
    for line in open(path):
        m = re.search(r'COMMENT/REPT,"(.*)"', line)
        if m:
            return m.group(1)
    return None


def read_report(path):
    part, res, cur = None, {}, None
    for line in open(path):
        m = re.match(r"PART NAME\s*:\s*(\S+)", line)
        if m:
            part = m.group(1)
        m = re.match(r"DIM (\S+)=", line)
        if m:
            cur = m.group(1)
            res[cur] = {}
            continue
        if "FEATURE NOT FOUND" in line and cur:
            res[cur] = None
        m = re.match(r"(X|Y|Z|D|L|W|DP)\s+(-?[\d.]+)\s+[\d.]+\s+[\d.]+\s+(-?[\d.]+)", line)
        if m and cur and res.get(cur) is not None:
            res[cur][m.group(1)] = float(m.group(3))
    return part, res
