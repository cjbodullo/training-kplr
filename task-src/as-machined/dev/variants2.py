#!/usr/bin/env python3
"""misread battery for the lot-day reconstruction: start from the true lot-day reading, change one
thing, rebuild the affected parts and grade them with the real verifier.
usage (dev image): variants2.py <truth dir> <work dir> [name ...]"""
import copy
import os
import sys
import time

sys.path.insert(0, "/w/solution")
sys.path.insert(0, "/w/tests")
import cadquery as cq  # noqa: E402
import check_models  # noqa: E402
import cut  # noqa: E402
import history  # noqa: E402
import parts  # noqa: E402

TRUE = history.load_state("/w/dev/state0918")
TODAY = history.load_state("/w/environment/data/cnc")
AXIS = {"MNF-0610": "Y", "BRG-1140": "X", "LVR-2205": "X"}
M, B, L = "MNF-0610", "BRG-1140", "LVR-2205"


def st(**chg):
    s = copy.deepcopy(TRUE)
    for path, v in chg.items():
        k = path.split("__")
        if k[0] == "param":
            s["params"][int(k[1])] = v
        elif k[0] == "work":
            s["work"][int(k[1])][int(k[2])] = v
        else:
            s["off"][k[0]][int(k[1])] = v
    return s


def today_with_old_t6():
    s = copy.deepcopy(TODAY)
    s["off"]["Hg"][6] = parts.OLD_T6[1]
    return s


V = {
    # history not used / partly used
    "today_state_no_rollback": [(p, dict(state=TODAY, old_t6=False)) for p in (M, B, L)],
    "today_state_plus_cmm_fixes": [(p, dict(state=today_with_old_t6(), work_fix=True)) for p in (M, B, L)],
    "dpi_not_rolled_back": [(B, dict(state=st(param__3401="P00000000")))],
    "ext_not_rolled_back": [(p, dict(state=st(work__0__2=-0.2))) for p in (M, B, L)],
    "h3_wear_not_rolled_back": [(M, dict(state=st(Hw__3=-0.05))), (B, dict(state=st(Hw__3=-0.05)))],
    "d7_wear_not_rolled_back": [(M, dict(state=st(Dw__7=0.12)))],
    # evidence not used
    "g56_shift_not_found": [(B, dict(state=st(work__3__0=-612.0)))],
    "t6_current_drill": [(p, dict(state=st(Hg__6=121.115), old_t6=False)) for p in (M, B, L)],
    "t6_old_drill_h6_left_current": [(p, dict(state=st(Hg__6=121.115))) for p in (M, B, L)],
    "op20_turned_about_x_as_setup_sheet": [(M, dict(axis="X"))],
    # control semantics, on the lot-day state
    "m98_own_local_level": [(M, dict(quirks={"m98_new_level"}))],
    "mirror_keeps_arc_direction": [(M, dict(quirks={"mirror_keeps_arcs"}))],
    "h_taken_from_tool_not_program": [(M, dict(quirks={"h_is_tool"}))],
    "g52_accumulates": [(B, dict(quirks={"g52_adds"}))],
    "vacant_argument_as_zero": [(B, dict(quirks={"vacant_is_zero"}))],
    "m99_restores_g90": [(L, dict(quirks={"m99_restores_g90"}))],
    "bull_nose_as_flat": [(L, dict(tools={9: cut.Tool("flat", 8.0)}))],
    # the rapid traverse scratch
    "rapids_do_not_cut": [(M, dict(no_rapids=True))],
    "rapids_do_not_cut_and_turned_about_x": [(M, dict(no_rapids=True, axis="X"))],
}


def build(part, state=None, old_t6=True, axis=None, quirks=(), tools=None, work_fix=False, no_rapids=False):
    t, ln = parts.crib(old_t6)
    if tools:
        t.update(tools)
    s = copy.deepcopy(state if state is not None else TRUE)
    if work_fix:       # the G56 shift the CMM shows, applied on top of an un-rolled-back state
        s["work"][3][0] += 0.3
    if no_rapids:
        orig = cut.sweeps
        cut.sweeps = lambda moves, tools, **kw: orig([m for m in moves if m[0] != "rapid"], tools, **kw)
        try:
            return parts.build(part, s, t, ln, axis or AXIS[part], quirks)
        finally:
            cut.sweeps = orig
    return parts.build(part, s, t, ln, axis or AXIS[part], quirks)


def main():
    truth, work = sys.argv[1], sys.argv[2]
    os.makedirs(work, exist_ok=True)
    only = set(sys.argv[3:])
    for name, runs in V.items():
        if only and name not in only:
            continue
        for part, kw in runs:
            t0 = time.time()
            try:
                s = build(part, **kw)
                path = f"{work}/{name}__{part}.step"
                cq.exporters.export(cq.Workplane().add(s), path)
                try:
                    msg = "PASS(!) " + check_models.compare(path, f"{truth}/{part}.step")
                except check_models.Bad as e:
                    msg = f"FAIL {e}"
            except Exception as e:
                msg = f"BUILD ERROR {type(e).__name__}: {e}"
            print(f"{name:36s} {part:9s} {msg}  [{time.time() - t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
