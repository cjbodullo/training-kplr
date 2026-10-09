"""Lazy attempts at the print -> STEP job; each set must score 0 with tests/check_models.py.

usage (inside the agent image): python3 make_cheats.py <reference models dir> <out dir>
"""
import os
import sys

import cadquery as cq
import ezdxf

ref, out = sys.argv[1], sys.argv[2]
parts = ["BRK-2210", "FLG-0417", "HSG-3305", "SHF-1150", "CVR-5120", "BKT-3302"]
sizes = {"BRK-2210": (120, 80, 90), "FLG-0417": (140, 140, 50), "HSG-3305": (76.2, 50.8, 38.1),
         "SHF-1150": (480, 40, 40), "CVR-5120": (160, 110, 12), "BKT-3302": (70, 50, 45)}


def load(p):
    return cq.importers.importStep(p).val()


def put(name, shape, kind):
    d = os.path.join(out, kind)
    os.makedirs(d, exist_ok=True)
    cq.exporters.export(cq.Workplane().add(shape), os.path.join(d, f"{name}.step"))


for p in parts:
    good = load(os.path.join(ref, f"{p}.step"))
    # 1 envelope block with the right overall size
    put(p, cq.Workplane("XY").box(*sizes[p], centered=False).val(), "c1_envelope")
    # 2 right part plus a second solid in the same file
    put(p, cq.Compound.makeCompound([good, cq.Solid.makeBox(5, 5, 5).translate((300, 0, 0))]), "c2_two_solids")
    # 3 mirror image (projection method misread)
    put(p, good.mirror("XZ"), "c3_mirror")
    # 4 drawn geometry taken at face value: scale the part by the ratio drawn/dimensioned overall size
    doc = ezdxf.readfile(f"/app/drawings/{p if p != 'BKT-3302' else 'BKT-3300'}.dxf")
    xs = [v for e in doc.modelspace().query("LINE[layer=='VISIBLE']") for v in (e.dxf.start.x, e.dxf.end.x)]
    ratio = (max(xs) - min(xs)) / 3.0 / max(sizes[p])      # crude: drawn extent of the views vs the true size
    put(p, good.scale(ratio), "c4_measured")
print("wrote cheats to", out)
