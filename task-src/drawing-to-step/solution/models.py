#!/usr/bin/env python3
"""Reference models for the three vendor prints, built in CadQuery 2.8 from the dimension text.

The prints are not to scale, so nothing is measured off the geometry; every value below is a
dimension or callout on the drawing. Axes follow each drawing's front view: X right, Z up, Y away.
"""
import math
import sys

import cadquery as cq

IN = 25.4
out = sys.argv[1] if len(sys.argv) > 1 else "/app/models"


def save(part, name):
    solid = part.val() if hasattr(part, "val") else part
    assert solid.isValid()
    cq.exporters.export(cq.Workplane().add(solid), f"{out}/{name}.step")
    print(name, round(solid.Volume(), 3))


# ------------------------------------------------------------------ BRK-2210  (first angle, mm)
# first angle: plan view sits below the elevation, the view from the LEFT sits to its right.
# so in the side view the 12 thick upright is at the back (Y 68..80) and the gusset is on the right.
base = cq.Workplane("XY").box(120, 80, 10, centered=False)                   # 120 x 80 x 10
upright = cq.Workplane("XY").box(80, 12, 90, centered=False).translate((10, 68, 0))   # 10 from left, 80 wide, 12, h 90
brk = base.union(upright)
gusset = (cq.Workplane("YZ").polyline([(68, 10), (68 - 40, 10), (68, 10 + 50)]).close()
          .extrude(6).translate((84, 0, 0)))                                  # 84 from left, 6 thick, legs 40 / 50
brk = brk.union(gusset)
brk = brk.edges(cq.selectors.BoxSelector((11, 67.5, 9.5), (83, 68.5, 10.5))).fillet(6)              # R6
brk = brk.edges(cq.selectors.BoxSelector((9, 67, 89), (91, 81, 91))).edges("|X").chamfer(2)          # 2X 2x45
brk = brk.edges(cq.selectors.BoxSelector((-1, -1, -1), (1, 1, 11))).edges("|Z").chamfer(5)          # 5x45
brk = brk.cut(cq.Workplane("XZ").center(50, 55).circle(52 / 2).extrude(-100))                       # 52 THRU at 50 / 55
for k in range(4):                                                             # 4X M5, drill 4.2 deep 10, PCD 63, 45 deg
    a = math.radians(45 + 90 * k)
    brk = brk.cut(cq.Workplane("XZ", origin=(0, 68, 0))
                  .center(50 + 31.5 * math.cos(a), 55 + 31.5 * math.sin(a)).circle(2.1).extrude(-10))
for x, y in [(18, 14), (102, 14), (18, 56), (102, 46)]:                       # 4X 6.6 THRU, cbore 11 deep 6.8
    brk = brk.cut(cq.Workplane("XY").center(x, y).circle(3.3).extrude(10))
    brk = brk.cut(cq.Workplane("XY", origin=(0, 0, 10 - 6.8)).center(x, y).circle(5.5).extrude(6.8))
for x, y in [(35, 50), (85, 20)]:                                             # 2X 5 H7 DP 8 FROM BOTTOM FACE (hidden circles in the plan)
    brk = brk.cut(cq.Workplane("XY").center(x, y).circle(5 / 2).extrude(8))
brk = brk.cut(cq.Workplane("XY").center(55, 32).slot2D(20 + 10, 10).extrude(10))   # slot R5, 20 c-c, at 55 / 32
brk = brk.cut(cq.Workplane("XY", origin=(0, 0, 10 - 4)).center(55, 32).slot2D(20 + 2 * 8, 16).extrude(4))  # R8 counter-slot, 4 deep (section B-B)
save(brk, "BRK-2210")

# ------------------------------------------------------------------ FLG-0417  (third angle, mm, section A-A)
flg = cq.Workplane("XY").circle(140 / 2).extrude(14).union(
    cq.Workplane("XY", origin=(0, 0, 14)).circle(70 / 2).extrude(50 - 14))  # 140 x 14 flange, 70 hub, overall 50
flg = flg.edges(cq.selectors.BoxSelector((-36, -36, 13), (36, 36, 15))).fillet(3)  # R3
flg = flg.faces(">Z").edges().chamfer(1)                                       # 1x45 on the hub
flg = flg.cut(cq.Workplane("XY").circle(25 / 2).extrude(50))                   # 25 H7 bore (nominal)
flg = flg.cut(cq.Workplane("XY").circle(40 / 2).extrude(6))                    # 40 counterbore deep 6, mounting face
kb = -25 / 2 + 28.3                                                            # 28.3 over bore + keyway
flg = flg.cut(cq.Workplane("XY").center(kb - 5, 0).rect(10, 8).extrude(50))    # keyway 8 wide, full length
for k in range(5):                                                             # 5X 11 THRU EQ SP on 110 PCD, first at 18 deg
    a = math.radians(18 + 72 * k)
    flg = flg.cut(cq.Workplane("XY").center(55 * math.cos(a), 55 * math.sin(a)).circle(5.5).extrude(14))
# O-ring groove (DETAIL A): bottom corners on dia 80, bottom width 5, depth 2.5, sides 5 deg off vertical
# opening towards the face, R0.4 in both bottom corners
d5 = math.tan(math.radians(5))
gp = (cq.Workplane("XZ").polyline([(80 / 2 - (2.5 + 2) * d5, -2), (80 / 2, 2.5), (80 / 2 + 5, 2.5),
                                   (80 / 2 + 5 + (2.5 + 2) * d5, -2)]).close().revolve(360, (0, 0, 0), (0, 1, 0)))
flg = flg.cut(gp)
flg = flg.edges(cq.selectors.BoxSelector((-50, -50, 2.3), (50, 50, 2.7))).fillet(0.4)   # 2X R0.4
save(flg, "FLG-0417")

# ------------------------------------------------------------------ HSG-3305  (third angle, inch -> mm)
L, W, H = 3.000 * IN, 2.000 * IN, 1.500 * IN
hsg = cq.Workplane("XY").box(L, W, H, centered=False)
t30 = math.radians(30)
x0 = 2.250 * IN                                                                # 30 deg face starts at 2.250
hsg = hsg.cut(cq.Workplane("XZ").polyline([(x0, H), (L + 5, H), (L + 5, H - (L + 5 - x0) * math.tan(t30))])
              .close().extrude(-W))
hsg = hsg.cut(cq.Workplane("YZ").center(1.000 * IN, 0.750 * IN).circle(0.750 / 2 * IN).extrude(1.250 * IN))  # port A
hsg = hsg.cut(cq.Workplane("YZ").center(1.000 * IN, 0.750 * IN).circle(0.500 / 2 * IN).extrude(2.000 * IN))
hsg = hsg.cut(cq.Workplane("XZ").center(1.500 * IN, 0.750 * IN).circle(0.375 / 2 * IN).extrude(-1.000 * IN))  # cross
for x, y in [(0.375, 0.375), (0.375, 1.625), (1.875, 0.375), (1.875, 1.625)]:  # 4X 1/4-20, drill .201 deep .500
    hsg = hsg.cut(cq.Workplane("XY", origin=(0, 0, H - 0.500 * IN)).center(x * IN, y * IN)
                  .circle(0.201 / 2 * IN).extrude(0.500 * IN))
# port B: .250 deep .500 normal to the 30 deg face, .400 down the slope from the 2.250 edge, on Y 1.000
cx, cz = x0 + 0.400 * IN * math.cos(t30), H - 0.400 * IN * math.sin(t30)
n = cq.Vector(math.sin(t30), 0, math.cos(t30))
start = cq.Vector(cx, 1.000 * IN, cz) + n * 2.0
hsg = hsg.cut(cq.Workplane().add(cq.Solid.makeCylinder(0.250 / 2 * IN, 0.500 * IN + 2.0, start, -n)))
# VIEW C: 2X 1/4-20 (drill .201 deep .500) normal to the 30 deg face, .650 down the slope, .375 and
# .375 + 1.250 from the front face
for yy in (0.375, 0.375 + 1.250):
    c = cq.Vector(x0 + 0.650 * IN * math.cos(t30), yy * IN, H - 0.650 * IN * math.sin(t30))
    hsg = hsg.cut(cq.Workplane().add(cq.Solid.makeCylinder(0.201 / 2 * IN, 0.500 * IN + 2.0, c + n * 2.0, -n)))
hsg = hsg.cut(cq.Workplane("XY").center((1.750 + 0.500) * IN, (0.500 + 0.375) * IN)
              .rect(1.000 * IN, 0.750 * IN).extrude(0.250 * IN).edges("|Z").fillet(0.125 * IN))  # pocket
save(hsg, "HSG-3305")

# ------------------------------------------------------------------ SHF-1150  (first angle, mm, broken view)
# the long dia 35 section is shortened on the print; lengths come from the dimension text only.
def seg(x0, x1, d):
    return cq.Workplane("YZ", origin=(x0, 0, 0)).circle(d / 2).extrude(x1 - x0)


# left end: TAPER 1:10 over the 40, dia 25 at the shoulder -> dia 25 - 40/10 = 21 at the end face
taper = cq.Workplane().add(cq.Solid.makeCone((25 - 40 / 10) / 2, 25 / 2, 40, cq.Vector(0, 0, 0), cq.Vector(1, 0, 0)))
shf = (taper.union(seg(40, 140, 30)).union(seg(140, 155, 40))   # taper 40 / 140 / collar 15
       .union(seg(155, 480 - 25, 35)).union(seg(480 - 25, 480, 30)))     # overall 480, end 25 at dia 30
shf = shf.faces(">X").chamfer(1.5)                                      # 1.5x45 on the right end only
# keyseat 8 wide, round ends, 60 from the left end, 50 long, bottom 26 over the underside (section B-B)
shf = shf.cut(cq.Workplane("XY", origin=(0, 0, 26 - 30 / 2)).center(60 + 25, 0).slot2D(50, 8).extrude(20))
# circlip groove dia 33 x 1.6, its right flank 10 from the dia 35 / dia 30 step
shf = shf.cut(cq.Workplane("YZ", origin=(455 - 10 - 1.6, 0, 0)).circle(25).circle(33 / 2).extrude(1.6))
# dia 6 thru 12 from the right end, seen as a circle in the front view -> drilled along Y (90 deg to the keyseat)
shf = shf.cut(cq.Workplane("XZ", origin=(0, 30, 0)).center(480 - 12, 0).circle(3).extrude(60))
# flat on the dia 35, 10 from the collar, 30 long, 32 across from the underside (section C-C), on top like the keyseat
shf = shf.cut(cq.Workplane("XY").box(30, 50, 10, centered=False).translate((155 + 10, -25, 32 - 35 / 2)))
save(shf, "SHF-1150")

# ------------------------------------------------------------------ CVR-5120  (third angle, mm, hole chart)
cvr = cq.Workplane("XY").box(160, 110, 12, centered=False).edges("|Z").fillet(10)   # 160 x 110 x 12, 4X R10
cvr = cvr.cut(cq.Workplane("XY", origin=(0, 0, 12 - 4)).center(70, 55).circle(40).extrude(4))  # C1 cbore 80 deep 4
cvr = cvr.cut(cq.Workplane("XY").center(70, 55).circle(20).extrude(12))                          # C1 40 thru
for k, (x, y) in enumerate([(12, 12), (148, 12), (148, 98), (12, 98), (130, 55), (12, 55)]):     # A1-A6
    cvr = cvr.cut(cq.Workplane("XY").center(x, y).circle(6.6 / 2).extrude(12))
    if k >= 4:   # A5, A6: CSK FAR SIDE -> the 90 deg countersink opens on the bottom face
        cone = cq.Solid.makeCone(13 / 2, 6.6 / 2, (13 - 6.6) / 2, cq.Vector(x, y, 0), cq.Vector(0, 0, 1))
    else:
        cone = cq.Solid.makeCone(6.6 / 2, 13 / 2, (13 - 6.6) / 2, cq.Vector(x, y, 12 - (13 - 6.6) / 2), cq.Vector(0, 0, 1))
    cvr = cvr.cut(cq.Workplane().add(cone))
for x, y in [(30, 25), (125, 85)]:                                       # B1, B2 M6, drill 5 deep 10 from bottom
    cvr = cvr.cut(cq.Workplane("XY").center(x, y).circle(5 / 2).extrude(10))
cvr = cvr.cut(cq.Workplane("XY").box(200, 8, 4, centered=False).translate((-20, 110 - 8, 0)))    # rabbet 8 x 4
cvr = cvr.edges(cq.selectors.BoxSelector((-1, 110 - 8 - 0.5, 3.5), (161, 110 - 8 + 0.5, 4.5))).fillet(3)  # note 4: R3 (side view)
save(cvr, "CVR-5120")

# ------------------------------------------------------------------ BKT-3302  (sheet BKT-3300, first angle, mm)
# the sheet shows BKT-3301 RH; note 2: BKT-3302 LH is the opposite hand, every feature mirrored.
# build the RH exactly as drawn, then mirror it.
rh = cq.Workplane("XY").box(70, 50, 20, centered=False)                                 # 70 x 50, base 20
rh = rh.union(cq.Workplane("XY").box(30, 50, 45 - 20, centered=False).translate((0, 0, 20)))  # tower 30 wide to 45
rh = rh.edges(cq.selectors.BoxSelector((29, -1, 44), (31, 51, 46))).chamfer(6)        # 6x45
rh = rh.cut(cq.Workplane("XY").box(10, 12, 8, centered=False).translate((70 - 10, 0, 0)))  # notch 10 x 12 x 8
rh = rh.edges(cq.selectors.BoxSelector((59.5, 11.5, -1), (60.5, 12.5, 9))).fillet(3)      # note 4: R3 (arc in the plan)
rh = rh.cut(cq.Workplane("XY").center(55, 25).slot2D(16 + 2 * 4, 8, 90).extrude(20))    # slot R4 thru, 16 c-c along Y
# view from below (first angle: it sits ABOVE the front view, Y reversed): 2X 4 H7 dowels 6 deep in the bottom face
for x, y in [(20, 10), (45, 40)]:
    rh = rh.cut(cq.Workplane("XY").center(x, y).circle(4 / 2).extrude(6))
for y in (15, 35):                                                                       # 2X M4: drill 3.3 deep 10
    rh = rh.cut(cq.Workplane("YZ", origin=(70, 0, 0)).center(y, 10).circle(3.3 / 2).extrude(-10))
# dia 8 thru: projected 20 deg off vertical in the front view (XZ), 30 deg off X in the plan (XY).
# a direction with those two projections: dx/dz = tan20, dy/dx = tan30
t20, t30 = math.tan(math.radians(20)), math.tan(math.radians(30))
axis = cq.Vector(t20, t20 * t30, -1.0).normalized()
entry = cq.Vector(12, 18, 45)                                                            # 12 from left, 18 from front
rh = rh.cut(cq.Workplane().add(cq.Solid.makeCylinder(8 / 2, 150, entry - axis * 30, axis)))
save(rh.mirror("YZ"), "BKT-3302")
