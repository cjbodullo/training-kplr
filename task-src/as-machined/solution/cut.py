#!/usr/bin/env python3
"""Material removal for the moves produced by fanuc.py, exact B-rep in CadQuery 2.8 / OCCT.

Every tool is a solid of revolution about Z with radius rho(h) at height h above the tip. Feed moves
are either pure Z (plunge: the tool at the low point, with its shank) or horizontal lines and arcs.
For a horizontal move the swept volume is exact:
  line : prism of the cross section {|u| <= rho(h)} along the segment, plus the tool at each end
  arc  : revolve of {|r - Rp| <= rho(h)} about the arc axis over the arc, plus the tool at each end
"""
import math

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Common
from OCP.TopTools import TopTools_ListOfShape

SHANK = 160.0
FUZZY = 1e-5          # sweeps that graze the same wall meet tangentially


class Tool:
    def __init__(self, kind, dia, corner=0.0, point=None, tip_flat=0.0):
        self.kind, self.R, self.rc, self.point, self.r0 = kind, dia / 2, corner, point, tip_flat / 2

    def half_profile(self, w):
        """closed outline in (u, h), u >= 0 half, drawn on workplane w (u -> x, h -> y)"""
        R, H = self.R, SHANK
        if self.kind == "flat":
            return w.moveTo(0, 0).lineTo(R, 0).lineTo(R, H).lineTo(0, H).close()
        if self.kind == "bull":
            pts = [(0, 0)] + self.corner_pts(0.0) + [(R, H), (0, H)]
            w = w.moveTo(*pts[0])
            for p in pts[1:]:
                w = w.lineTo(*p)
            return w.close()
        if self.kind == "cone":
            hc = (R - self.r0) / math.tan(math.radians(self.point / 2))
            w = w.moveTo(0, 0)
            if self.r0 > 0:
                w = w.lineTo(self.r0, 0)
            return w.lineTo(R, hc).lineTo(R, H).lineTo(0, H).close()
        raise ValueError(self.kind)

    def corner_pts(self, shift):
        """bull nose corner radius as a 24 segment polyline, sagitta 5e-4 mm at R1. torus against
        torus tangencies between neighbouring sweeps defeat the OCCT booleans; planes and cones
        do not, and 5e-4 mm is 40 times under the 0.02 mm the models are held to"""
        R, rc, n = self.R, self.rc, 24
        return [(shift + R - rc + rc * math.sin(math.pi / 2 * k / n), rc - rc * math.cos(math.pi / 2 * k / n))
                for k in range(n + 1)]

    def section(self, w, shift, poly=True):
        """full cross section {shift - rho(h) <= u <= shift + rho(h)}"""
        R, H = self.R, SHANK
        if self.kind == "flat":
            return (w.moveTo(shift - R, 0).lineTo(shift + R, 0).lineTo(shift + R, H)
                    .lineTo(shift - R, H).close())
        if self.kind == "bull" and poly:
            rc, n = self.rc, 24
            right = self.corner_pts(shift)
            left = [(2 * shift - u, h) for u, h in reversed(right)]
            pts = right + [(shift + R, H), (shift - R, H)] + left
            w = w.moveTo(*pts[0])
            for p in pts[1:]:
                w = w.lineTo(*p)
            return w.close()
        if self.kind == "bull":
            rc = self.rc
            return (w.moveTo(shift - R + rc, 0).lineTo(shift + R - rc, 0)
                    .radiusArc((shift + R, rc), -rc).lineTo(shift + R, H).lineTo(shift - R, H)
                    .lineTo(shift - R, rc).radiusArc((shift - R + rc, 0), -rc).close())
        if self.kind == "cone":
            hc = (R - self.r0) / math.tan(math.radians(self.point / 2))
            pts = [(shift - self.r0, 0)]
            if self.r0 > 0:
                pts.append((shift + self.r0, 0))
            pts += [(shift + R, hc), (shift + R, H), (shift - R, H), (shift - R, hc)]
            w = w.moveTo(*pts[0])
            for p in pts[1:]:
                w = w.lineTo(*p)
            return w.close()
        raise ValueError(self.kind)

    def at(self, p):
        wp = cq.Workplane(cq.Plane(origin=p, xDir=(1, 0, 0), normal=(0, -1, 0)))
        return self.half_profile(wp).revolve(360, (0, 0, 0), (0, 1, 0)).val()

    def line(self, p0, p1):
        d = (p1[0] - p0[0], p1[1] - p0[1])
        L = math.hypot(*d)
        d = (d[0] / L, d[1] / L)
        n = (-d[1], d[0], 0)
        wp = cq.Workplane(cq.Plane(origin=p0, xDir=n, normal=(d[0], d[1], 0)))
        return self.section(wp, 0.0).extrude(L).val()

    def arc(self, p0, p1, c, ccw):
        if not ccw:
            p0, p1 = p1, p0
        a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
        a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
        sweep = math.degrees(a1 - a0) % 360.0
        if sweep < 1e-7:
            sweep = 360.0
        Rp = math.hypot(p0[0] - c[0], p0[1] - c[1])
        e1 = ((p0[0] - c[0]) / Rp, (p0[1] - c[1]) / Rp, 0)
        # local y must be +Z: normal x xDir = Z  ->  normal = (e1y, -e1x, 0)
        plane = cq.Plane(origin=(c[0], c[1], p0[2]), xDir=e1, normal=(e1[1], -e1[0], 0))
        if abs(Rp - self.R) < 1e-9:
            Rp = self.R
        wire = self.section(cq.Workplane(plane), Rp).val()
        face = cq.Face.makeFromWires(wire)
        if Rp < self.R:
            # path circle smaller than the tool: everything from the axis out is swept inside the
            # sector (points outside it are covered by the tools at the two ends)
            w = Rp + self.R + 1
            keep = cq.Face.makeFromWires(cq.Workplane(plane).center(w / 2, SHANK / 2)
                                         .rect(w, SHANK + 2).val())
            face = face.intersect(keep)
            fs = face.Faces()
            if len(fs) != 1:
                raise RuntimeError("clipped section is not one face")
            face = fs[0]
        ax0 = cq.Vector(c[0], c[1], p0[2])
        return cq.Solid.revolve(face, sweep, ax0, ax0 + cq.Vector(0, 0, 1))


def sweeps(moves, tools, z_eps=1e-7, ztop=None):
    """solids swept by the moves. a rapid cuts whatever it passes through just like a feed does
    (G00 here is linear interpolation type positioning, 1401#1 LRP = 1, so its path is the straight
    line); moves that stay above `ztop` cannot touch the stock and are skipped"""
    out = []
    for kind, t, p0, p1, arc in moves:
        if ztop is not None and min(p0[2], p1[2]) > ztop + 1e-6:
            continue
        tool = tools[t]
        dz = p1[2] - p0[2]
        dxy = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if arc is not None:
            out.append(tool.arc(p0, p1, arc[0], arc[1]))
            out.append(tool.at(p1))
        elif dxy < 1e-9:
            out.append(tool.at(p1 if dz < 0 else p0))
        elif abs(dz) < z_eps:
            out.append(tool.line(p0, p1))
            out.append(tool.at(p0))
            out.append(tool.at(p1))
        else:
            raise ValueError(f"feed move with both XY and Z: {p0} -> {p1}")
    bad = [k for k, x in enumerate(out) if not x.isValid()]
    if bad:
        raise RuntimeError(f"invalid swept solids: {bad}")
    return out


def cut_one(stock, tool):
    args, tl = TopTools_ListOfShape(), TopTools_ListOfShape()
    args.Append(stock.wrapped)
    tl.Append(tool.wrapped)
    op = BRepAlgoAPI_Cut()
    op.SetArguments(args)
    op.SetTools(tl)
    op.SetFuzzyValue(FUZZY)
    op.Build()
    if not op.IsDone():
        raise RuntimeError("boolean cut failed")
    return cq.Shape.cast(op.Shape())


def cut(stock, solids):
    """remove the swept solids one at a time. a single boolean with hundreds of overlapping
    tools mis-classifies whole pieces on these parts; one at a time stays exact and checkable"""
    part = stock
    for k, s in enumerate(solids):
        r = cut_one(part, s)
        pieces = [x for x in r.Solids() if abs(x.Volume()) > 1e-6]
        if len(pieces) != 1 or not pieces[0].isValid():
            raise RuntimeError(f"cut {k}: pieces {[round(x.Volume(), 4) for x in pieces]}, "
                               f"valid={[x.isValid() for x in pieces]}")
        part = pieces[0]
    return part


def overlap(a, b):
    op = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
    return cq.Shape.cast(op.Shape()).Volume()


def rapid_hits(moves, tools, stock):
    """volume of finished material any rapid passes through (should be zero); straight
    retracts out of a cut are skipped"""
    worst = 0.0
    for kind, t, p0, p1, arc in moves:
        if kind != "rapid":
            continue
        if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) < 1e-9 and p1[2] >= p0[2]:
            continue
        tool = tools[t]
        dz = p1[2] - p0[2]
        dxy = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if dxy < 1e-9:
            s = [tool.at(p1 if dz < 0 else p0)]
        elif abs(dz) < 1e-7:
            s = [tool.line(p0, p1), tool.at(p0), tool.at(p1)]
        else:
            s = [tool.at(p0), tool.at(p1)]
            n = int(dxy) + 2
            for k in range(1, n):
                f = k / n
                s.append(tool.at(tuple(p0[i] + f * (p1[i] - p0[i]) for i in range(3))))
        for x in s:
            v = overlap(stock, x)
            if v > 1e-6:
                worst = max(worst, v)
                print("RAPID HIT", t, p0, p1, round(v, 4))
    return worst
