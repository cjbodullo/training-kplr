#!/usr/bin/env python3
"""As-machined STEP models of the lot that ran 2026-09-18.

1. roll today's control backup back to the lot date with the operation history (OPRT-HIS.TXT);
2. what the history cannot reach (it starts 09-24) is settled against the CMM reports of that lot:
   for each open question (which T6 was in the spindle, how MNF-0610 OP20 was loaded, any work
   offset moved) machine the part, measure it like the QC program does, compare, and fit work
   offset shifts from the positional residuals;
3. keep the one reading that reproduces every reported characteristic within CMM noise, export.

usage: models.py <cnc dir> <shop dir> <qc dir> <out dir>
"""
import glob
import sys

import cadquery as cq

import cmm
import history
import parts

LOT = "2026/09/18 23:59:59"
WCS = {"MNF-0610": 2, "BRG-1140": 3, "LVR-2205": 4}       # last setup's work offset (G55/G56/G57)
FIT_TOL = 0.01     # three serials, sigma ~1.5 um: anything real sits well inside this


def measured(qc):
    """average of the serials per characteristic; None where a report says not found"""
    acc = {}
    for path in sorted(glob.glob(f"{qc}/*.TXT")):
        part, res = cmm.read_report(path)
        for name, vals in res.items():
            acc.setdefault(part, {}).setdefault(name, []).append(vals)
    out = {}
    for part, chars in acc.items():
        out[part] = {}
        for name, runs in chars.items():
            if any(r is None for r in runs):
                out[part][name] = None
                continue
            out[part][name] = {ax: sum(r[ax] for r in runs) / len(runs) for ax in runs[0]}
    return out


def compare(part, solid, axis, meas):
    """residuals (measured - model) per characteristic axis; missing features count as huge"""
    model = cmm.inspect(part, parts.to_print(part, solid, axis))
    res = {}
    for name, m in meas.items():
        s = model.get(name)
        if (m is None) != (s is None):
            res[(name, "found")] = 99.0
            continue
        if m is None:
            continue
        for ax, v in m.items():
            res[(name, ax)] = v - s[ax]
    return res


def comments(qc):
    out = {}
    for path in sorted(glob.glob(f"{qc}/*.TXT")):
        part, _ = cmm.read_report(path)
        c = cmm.read_comment(path)
        if c:
            out.setdefault(part, set()).add(c)
    return {k: v.pop() if len(v) == 1 else sorted(v) for k, v in out.items()}


def marks_match(part, solid, axis, remark):
    """the inspector's visual note against the marks the modelled part carries on datum A"""
    model = cmm.scratch_comment(cmm.scratches(parts.to_print(part, solid, axis)))
    return model == remark


def worst(res):
    return max(abs(v) for v in res.values()) if res else 0.0


def shift_of(res):
    xs = [v for (n, ax), v in res.items() if ax == "X"]
    ys = [v for (n, ax), v in res.items() if ax == "Y"]
    return (round(sum(xs) / len(xs), 3) if xs else 0.0, round(sum(ys) / len(ys), 3) if ys else 0.0)


def settle(part, state, old_t6, axis, meas):
    """machine, compare, and if the residuals are a common XY offset, move that work offset"""
    tools, lengths = parts.crib(old_t6)
    st = dict(state, work={k: list(v) for k, v in state["work"].items()},
              off={k: dict(v) for k, v in state["off"].items()})
    if old_t6:      # H6 was re-entered from the presetter on 09-22, so it held the old drill
        st["off"]["Hg"][6] = parts.OLD_T6[1]
    s = parts.build(part, st, tools, lengths, axis)
    res = compare(part, s, axis, meas)
    if worst(res) > FIT_TOL and all(v < 99 for v in res.values()):
        dx, dy = shift_of(res)
        st["work"][WCS[part]][0] += dx
        st["work"][WCS[part]][1] += dy
        s = parts.build(part, st, tools, lengths, axis)
        res = compare(part, s, axis, meas)
        print(f"  {part}: work offset P{WCS[part]} moved by X{dx:+.3f} Y{dy:+.3f}", flush=True)
    return s, res


def main():
    cnc, shop, qc, out = sys.argv[1:5]
    today = history.load_state(cnc)
    state, undone, edits = history.roll_back(today, f"{cnc}/OPRT-HIS.TXT", LOT)
    print(f"history reaches back to {history.earliest(cnc + '/OPRT-HIS.TXT')}; undid {len(undone)} changes")
    for stamp, what in undone:
        print("  ", stamp, what)
    used = {1140, 1141, 1610, 1611, 1620, 1621, 2205, 2206, 9010, 9011, 9020}
    if used & set(edits):
        raise SystemExit(f"programs {used & set(edits)} were edited after the lot: cannot reconstruct")
    meas = measured(qc)
    remarks = comments(qc)
    found = {}
    for old_t6 in (False, True):            # TOOL-LIST: T6 was swapped on 09-22
        found = {}
        for part in ("BRG-1140", "LVR-2205", "MNF-0610"):
            for axis in (("X", "Y") if part == "MNF-0610" else ("X",)):
                s, res = settle(part, state, old_t6, axis, meas[part])
                print(f"T6 {'old' if old_t6 else 'current'} {part} OP20 axis {axis}: worst residual {worst(res):.4f}",
                      flush=True)
                ok_marks = marks_match(part, s, axis, remarks.get(part))
                print(f"    marks on datum A agree with the QC note: {ok_marks}", flush=True)
                if worst(res) <= FIT_TOL and ok_marks:
                    found[part] = s
                    break
            if part not in found:
                break
        if len(found) == 3:
            break
    if len(found) != 3:
        raise SystemExit("no reading of the lot reproduces the CMM reports")
    for name, s in found.items():
        cq.exporters.export(cq.Workplane().add(s), f"{out}/{name}.step")
        print(name, round(s.Volume(), 4), len(s.Faces()), "faces")


if __name__ == "__main__":
    main()
