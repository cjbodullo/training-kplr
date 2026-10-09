"""grade /app/am_peak.add.xml: controller rules, then real sumo over the sealed term time am peaks.

the agent's file is never handed to sumo. its phase durations and offsets are read, checked against the
controller specification (the existing program's stage and interstage structure), and a clean tlLogic is
written from them. that program then runs on the sealed days.
"""
import os
import subprocess
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import pytest

AGENT = "/app/am_peak.add.xml"
SEALED = "/tests/sealed"
WORK = "/tmp/grade"
JUNCTIONS = ["J1", "J2", "J3", "J4"]
MIN_GREEN = {"J1": [10, 7, 9], "J2": [10, 7, 9], "J3": [10, 7, 9], "J4": [10, 7]}
PED_STAGE = {"J1": 2, "J2": 2, "J3": 2}       # all red pedestrian stage index, fixed at 9 s
MAX_CYCLE = 120
DAYS = sorted(f[:-8] for f in os.listdir(SEALED) if f.endswith(".rou.xml"))
BEGIN, END = 6.75 * 3600, 11.0 * 3600
MAX_DEPART_DELAY = 300.0     # s a vehicle may wait to get into the model at any entry
MAX_BLOCK_BACK = 120         # s per link per day a queue may reach back to the upstream stop line
BB_GAP = 8.0


def _spec():
    root = ET.parse(os.path.join(SEALED, "existing.add.xml")).getroot()
    return {tl.get("id"): [(p.get("state"), int(float(p.get("duration")))) for p in tl.iter("phase")]
            for tl in root.iter("tlLogic")}


def _num(v, what):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise AssertionError(f"{what}: not a number ({v!r})")
    assert f == int(f), f"{what}: whole seconds only ({v})"
    return int(f)


def _read_plan():
    assert os.path.isfile(AGENT), f"{AGENT} missing"
    try:
        root = ET.parse(AGENT).getroot()
    except ET.ParseError as e:
        raise AssertionError(f"{AGENT} is not valid xml: {e}")
    spec = _spec()
    plan = {}
    for j in JUNCTIONS:
        tls = [t for t in root.iter("tlLogic") if t.get("id") == j and t.get("programID") == "am_peak"]
        assert len(tls) == 1, f"{j}: expected exactly one tlLogic programID am_peak, found {len(tls)}"
        tl = tls[0]
        assert tl.get("type", "static") == "static", f"{j}: must be a static (fixed time) program"
        phases = list(tl.iter("phase"))
        ref = spec[j]
        assert len(phases) == len(ref), f"{j}: {len(phases)} phases, the controller runs {len(ref)}"
        durs = []
        for i, (p, (st, d)) in enumerate(zip(phases, ref)):
            assert p.get("state") == st, f"{j} phase {i}: state {p.get('state')} is not the controller's {st}"
            dur = _num(p.get("duration"), f"{j} phase {i} duration")
            if i % 4 == 0:
                stage = i // 4
                if PED_STAGE.get(j) == stage:
                    assert dur == 9, f"{j}: pedestrian stage must stay 9 s (got {dur})"
                assert dur >= MIN_GREEN[j][stage], f"{j} stage {stage + 1}: {dur} s under its minimum green"
            else:
                assert dur == d, f"{j} phase {i}: interstage periods are fixed ({d} s), got {dur}"
            durs.append((st, dur))
        off = _num(tl.get("offset", "0"), f"{j} offset")
        plan[j] = (durs, off)
    cycles = {j: sum(d for _, d in plan[j][0]) for j in plan}
    assert len(set(cycles.values())) == 1, f"junctions must share one cycle time: {cycles}"
    c = cycles["J1"]
    assert c <= MAX_CYCLE, f"cycle {c} s over the {MAX_CYCLE} s maximum"
    for j in plan:
        assert 0 <= plan[j][1] < c, f"{j}: offset {plan[j][1]} outside 0..{c - 1}"
    return plan


def _write_clean(plan, path):
    with open(path, "w") as f:
        f.write("<additional>\n")
        for j in JUNCTIONS:
            durs, off = plan[j]
            f.write(f'    <tlLogic id="{j}" type="static" programID="am_peak" offset="{off}">\n')
            for st, d in durs:
                f.write(f'        <phase duration="{d}" state="{st}"/>\n')
            f.write("    </tlLogic>\n")
        f.write("</additional>\n")


def _lane_lengths():
    out = {}
    for ln in ET.parse(os.path.join(SEALED, "corridor.net.xml")).getroot().iter("lane"):
        out[ln.get("id")] = float(ln.get("length"))
    return out


def _run(day, plan_file):
    wd = os.path.join(WORK, day)
    os.makedirs(wd, exist_ok=True)
    with open(os.path.join(SEALED, "bb.add.xml")) as s, open(os.path.join(wd, "bb.add.xml"), "w") as d:
        d.write(s.read())
    cmd = ["sumo", "-n", os.path.join(SEALED, "corridor.net.xml"), "-r", os.path.join(SEALED, day + ".rou.xml"),
           "-a", plan_file + "," + os.path.join(wd, "bb.add.xml"),
           "--begin", str(int(BEGIN)), "--end", str(int(END)), "--seed", "1",
           "--tripinfo-output", os.path.join(wd, "trips.xml"), "--statistic-output", os.path.join(wd, "stats.xml"),
           "--time-to-teleport", "300", "--no-step-log", "true", "--duration-log.disable", "true",
           "--xml-validation", "never"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=wd, timeout=1200)
    return r.returncode, r.stderr[-1500:]


def _metrics(day):
    wd = os.path.join(WORK, day)
    st = ET.parse(os.path.join(wd, "stats.xml")).getroot()
    loaded = int(st.find("vehicles").get("loaded"))
    trips = list(ET.parse(os.path.join(wd, "trips.xml")).getroot().iter("tripinfo"))
    lengths = _lane_lengths()
    bb = {}
    for iv in ET.parse(os.path.join(wd, "bb.xml")).getroot():
        lid = iv.get("id")[3:]
        if float(iv.get("maxJamLengthInMeters", "0")) >= lengths[lid] - BB_GAP:
            bb[lid] = bb.get(lid, 0) + 1
    return {"teleports": int(st.find("teleports").get("total")), "loaded": loaded, "arrived": len(trips),
            "depart_delay": max((float(t.get("departDelay")) for t in trips), default=0.0),
            "block_back": bb}


@pytest.fixture(scope="session")
def results():
    plan = _read_plan()
    os.makedirs(WORK, exist_ok=True)
    pf = os.path.join(WORK, "am_peak.clean.add.xml")
    _write_clean(plan, pf)
    with ThreadPoolExecutor(max_workers=min(len(DAYS), os.cpu_count() or 2)) as ex:
        runs = dict(zip(DAYS, ex.map(lambda d: _run(d, pf), DAYS)))
    out = {}
    for d, (rc, err) in runs.items():
        out[d] = _metrics(d) if rc == 0 else {"error": err}
        print(d, out[d])
    return out


def test_controller_rules():
    _read_plan()


def test_sealed_days_found():
    assert len(DAYS) == 10, DAYS


@pytest.mark.parametrize("day", DAYS)
def test_day(results, day):
    m = results[day]
    assert "error" not in m, f"sumo failed: {m.get('error')}"
    assert m["teleports"] == 0, f"{m['teleports']} teleports (gridlock)"
    assert m["arrived"] == m["loaded"], f"only {m['arrived']} of {m['loaded']} vehicles got through by 11:00"
    assert m["depart_delay"] <= MAX_DEPART_DELAY, \
        f"queue past the edge of the model: a vehicle waited {m['depart_delay']:.0f} s to enter"
    worst = max(m["block_back"].items(), key=lambda kv: kv[1], default=(None, 0))
    assert worst[1] <= MAX_BLOCK_BACK, f"blocking back on {worst[0]} for {worst[1]} s"
