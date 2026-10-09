#!/usr/bin/env python3
"""roll the control backup back to a past date using the operation history export (OPRT-HIS.TXT).
every logged data change after the cut-off is undone (new value -> old value), newest first."""
import copy
import re

import fanuc

WORK_NO = {"EXT": 0, "G54": 1, "G55": 2, "G56": 3, "G57": 4, "G58": 5, "G59": 6}


def _norm(v):
    v = v.lstrip("P")
    if re.fullmatch(r"[01]{8}", v):
        return v
    return float(v)


def load_state(cnc):
    return {"progs": fanuc.load_programs(f"{cnc}/ALL-PROG.TXT"),
            "params": fanuc.read_params(f"{cnc}/CNC-PARA.TXT"),
            "off": fanuc.read_offsets(f"{cnc}/TOOLOFST.TXT"),
            "work": fanuc.read_work(f"{cnc}/EXT_WKZ.TXT")}


def events(path):
    out = []
    for line in open(path):
        m = re.match(r"\d{5}\s+(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d)\s+(.*\S)", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def earliest(path):
    return min(t for t, _ in events(path))


def roll_back(state, path, before):
    """state as it was at `before` ("YYYY/MM/DD HH:MM:SS"), as far as the history reaches.
    returns (state, list of undone changes, list of program edits that cannot be undone)"""
    st = copy.deepcopy(state)
    undone, edits = [], []
    for stamp, what in sorted(events(path), reverse=True):
        if stamp <= before:
            break
        m = re.match(r"(WEAR|GEOM) OFFSET \((H|D)\)\s+NO\.(\d+)\s+(-?[\d.]+)\s+->\s+(-?[\d.]+)", what)
        if m:
            key = ("H" if m.group(2) == "H" else "D") + ("w" if m.group(1) == "WEAR" else "g")
            no, old, new = int(m.group(3)), float(m.group(4)), float(m.group(5))
            if abs(st["off"][key].get(no, 0.0) - new) > 1e-9:
                raise ValueError(f"history does not chain at {stamp}: {what}")
            st["off"][key][no] = old
            undone.append((stamp, what))
            continue
        m = re.match(r"WORK OFFSET\s+(\w+)\s+([XYZ])\s+(-?[\d.]+)\s+->\s+(-?[\d.]+)", what)
        if m:
            no, ax = WORK_NO[m.group(1)], "XYZ".index(m.group(2))
            old, new = float(m.group(3)), float(m.group(4))
            if abs(st["work"][no][ax] - new) > 1e-9:
                raise ValueError(f"history does not chain at {stamp}: {what}")
            st["work"][no][ax] = old
            undone.append((stamp, what))
            continue
        m = re.match(r"PARAMETER\s+NO\.(\d+)\s+(\S+)\s+->\s+(\S+)", what)
        if m:
            no, old, new = int(m.group(1)), m.group(2), m.group(3)
            if _norm(st["params"].get(no, "")) != _norm(new):
                raise ValueError(f"history does not chain at {stamp}: {what}")
            st["params"][no] = "P" + old
            undone.append((stamp, what))
            continue
        m = re.match(r"PROGRAM EDIT\s+O(\d+)", what)
        if m:
            edits.append(int(m.group(1)))
    return st, undone, edits
