#!/usr/bin/env python3
"""sealed truth + QC evidence: machine the three parts on the lot-day state (dev/state0918, old T6,
MNF OP20 turned over about Y), export tests/truth/*.step, and write the CMM reports of three
serials per part into environment/data/qc/."""
import json
import os
import random
import sys

sys.path.insert(0, "/w/solution")
import cadquery as cq  # noqa: E402
import cmm  # noqa: E402
import parts  # noqa: E402

STATE = "/w/dev/state0918"
AXIS = {"MNF-0610": "Y", "BRG-1140": "X", "LVR-2205": "X"}
random.seed(91826)
os.makedirs("/w/environment/data/qc", exist_ok=True)
tools, lengths = parts.crib(old_t6=True)
summary = {}
for part in ("MNF-0610", "BRG-1140", "LVR-2205"):
    s = parts.build(part, STATE, tools, lengths, AXIS[part], check=True)
    cq.exporters.export(cq.Workplane().add(s), f"/w/tests/truth/{part}.step")
    printed = parts.to_print(part, s, AXIS[part])
    res = cmm.inspect(part, printed)
    runs = cmm.scratches(printed) if part == "MNF-0610" else []
    comment = cmm.scratch_comment(runs)
    print(part, "scratch runs", runs, comment, flush=True)
    summary[part] = res
    for k, ser in enumerate(("0918-02", "0918-05", "0918-11")):
        cmm.write_report(part, ser, "9/18/2026", res, lambda: random.gauss(0, 0.0015),
                         f"/w/environment/data/qc/{part}_{ser}.TXT", comment)
    print(part, round(s.Volume(), 4), json.dumps({k: (None if v is None else {a: round(b, 4) for a, b in v.items()}) for k, v in res.items()}), flush=True)
