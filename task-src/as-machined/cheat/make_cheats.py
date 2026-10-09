"""Lazy attempts at the as-machined STEP job; each set must score 0 with tests/test.sh.

usage (inside the agent image): python3 make_cheats.py <correct models dir> <out dir>
"""
import os
import sys

import cadquery as cq

ref, out = sys.argv[1], sys.argv[2]
parts = {"MNF-0610": (120, 80, 26.0), "BRG-1140": (90, 60, 40), "LVR-2205": (110, 45, 20)}


def put(name, shape, kind):
    d = os.path.join(out, kind)
    os.makedirs(d, exist_ok=True)
    cq.exporters.export(cq.Workplane().add(shape), os.path.join(d, f"{name}.step"))


for p, size in parts.items():
    good = cq.importers.importStep(os.path.join(ref, f"{p}.step")).val()
    # 1 envelope block with the right overall size
    put(p, cq.Workplane("XY").box(*size, centered=False).val(), "c1_envelope")
    # 2 right part plus a second solid in the same file
    bb = good.BoundingBox()
    put(p, cq.Compound.makeCompound([good, cq.Solid.makeBox(5, 5, 5).translate((bb.xmax + 50, 0, 0))]),
        "c2_two_solids")
    # 3 mirror image
    put(p, good.mirror("XZ"), "c3_mirror")
    # 4 right part scaled to inch by mistake
    put(p, good.scale(25.4), "c4_inch")
print("wrote cheats to", out)
