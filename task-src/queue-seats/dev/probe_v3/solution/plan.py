"""reference planner: estimate the call centre's behaviour from queue_log, then size each
half hour of the plan week by simulation.
usage: python3 plan.py QUEUE_LOG FORECAST_CSV QSIM_BINARY OUT_CSV"""
import collections
import csv
import datetime as dt
import math
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np

WRAP_NEW = {"billing": 15, "moving": 30, "faults": 60}   # queues.conf as of march
TIMEOUT = {"billing": 0, "moving": 0, "faults": 600}     # extensions.conf Queue() timeout
XFER_TARGET = {"6002": "moving"}
SLT, GHOST, SL_T, AB_T = 20, 10, 0.80, 0.05
NS = 200000
NARR = int(os.environ.get("PLAN_NARR", "400000"))
NAIVE_TALK = os.environ.get("PLAN_TALK") == "all"   # dev ablation only
TMP = tempfile.mkdtemp(prefix="plan_")
QSIM = sys.argv[3] if len(sys.argv) > 3 else "qsim"


def block(ts):
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    return blk(d.date(), d.hour)


def blk(day, hour):
    wd = day.weekday()
    if wd == 5:
        return "sat"
    part = "am" if hour < 12 else ("pm" if hour < 17 else "eve")
    return ("mon_" if wd == 0 else "wk_") + part


def parse(path):
    calls = {}       # (callid, queue) -> dict
    agent_ev = collections.defaultdict(list)   # (queue, agent) -> [(t, ev, data)]
    xfer_ids = set()
    with open(path) as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            t, cid, q, ag, ev = int(p[0]), p[1], p[2], p[3], p[4]
            data = p[5:]
            if ev in ("PAUSE", "UNPAUSE", "ADDMEMBER", "REMOVEMEMBER"):
                agent_ev[(q, ag)].append((t, ev, data[0] if data else ""))
                continue
            if cid == "NONE":
                continue
            c = calls.setdefault((cid, q), {"q": q})
            if ev == "ENTERQUEUE":
                c["enter"] = t
                c["xfer_in"] = cid in xfer_ids
            elif ev == "CONNECT":
                c["hold"] = int(data[0]); c["ring"] = int(data[2]); c["agent"] = ag
            elif ev in ("COMPLETECALLER", "COMPLETEAGENT"):
                c["talk"] = int(data[1]); c["end"] = t; c["agent"] = ag
            elif ev == "BLINDTRANSFER":
                c["talk"] = int(data[3]); c["end"] = t; c["agent"] = ag; c["xfer"] = XFER_TARGET.get(data[0])
                xfer_ids.add(cid)
            elif ev == "ABANDON":
                c["aband"] = int(data[2])
            elif ev == "EXITWITHTIMEOUT":
                c["tmo"] = int(data[2])
    return calls, agent_ev


def attach_after_call(calls, agent_ev):
    """store on each finished call the span from call end to the end of a manual ACW pause
    that starts right after it (0 when the agent did not pause, None when unreadable)"""
    ends = collections.defaultdict(list)
    for c in calls.values():
        if "end" in c:
            ends[(c["q"], c["agent"])].append(c)
    for key, cs in ends.items():
        evs = sorted(e for e in agent_ev.get(key, []) if e[2] == "ACW")
        pauses = [e[0] for e in evs if e[1] == "PAUSE"]
        unp = [e[0] for e in evs if e[1] == "UNPAUSE"]
        pi = 0
        for c in sorted(cs, key=lambda x: x["end"]):
            e = c["end"]
            while pi < len(pauses) and pauses[pi] < e:
                pi += 1
            if pi < len(pauses) and pauses[pi] - e <= 12:
                u = next((x for x in unp if x >= pauses[pi]), None)
                c["span"] = u - e + 0.5 if u is not None else None
            else:
                c["span"] = 0.0


def resample_days(calls, rng):
    """day block bootstrap of the history, stratified by weekday. used to measure how far six
    weeks of data pin the answer down; the reference itself uses the data as it is."""
    by_day = collections.defaultdict(list)
    for c in calls:
        if "enter" in c:
            by_day[dt.datetime.fromtimestamp(c["enter"], dt.timezone.utc).date()].append(c)
    by_wd = collections.defaultdict(list)
    for d in sorted(by_day):
        by_wd[d.weekday()].append(d)
    out = []
    for wd in sorted(by_wd):
        days = by_wd[wd]
        for i in rng.choice(len(days), len(days)):
            out += by_day[days[i]]
    return out


def km_samples(obs, rng, n):
    """obs: list of (time, abandoned bool). sample patience from kaplan meier, jittered."""
    obs = sorted(obs)
    times = np.array([o[0] for o in obs], float)
    ev = np.array([o[1] for o in obs], bool)
    uniq = np.unique(times[ev])
    surv = []
    s = 1.0
    for u in uniq:
        nrisk = len(times) - np.searchsorted(times, u, side="left")
        d = np.sum((times == u) & ev)
        s *= 1 - d / nrisk
        surv.append(s)
    cdf = 1 - np.array(surv)
    u = rng.random(n)
    idx = np.searchsorted(cdf, u, side="left")
    out = np.empty(n)
    inside = idx < len(uniq)
    out[inside] = uniq[idx[inside]] + rng.uniform(-0.5, 0.5, inside.sum())
    # tail beyond the last observed abandon: exponential continuation
    out[~inside] = uniq[-1] + rng.exponential(600.0, (~inside).sum())
    return np.maximum(out, 0.05)


def wfile(name, arr):
    p = os.path.join(TMP, name)
    np.savetxt(p, arr, fmt="%.3f")
    return p


def build_models(calls, seed=7, tag=""):
    """calls: list of call dicts carrying their after call span"""
    rng = np.random.default_rng(seed)
    files = {}
    for q in ("billing", "moving", "faults"):
        cs = [c for c in calls if c["q"] == q and "enter" in c]
        for kind in ("fresh", "xfer_in"):
            sub = [c for c in cs if c["xfer_in"] == (kind == "xfer_in")]
            if not sub:
                continue
            obs = []
            for c in sub:
                if "aband" in c:
                    obs.append((c["aband"], True))
                elif "hold" in c:
                    obs.append((c["hold"], False))
                elif "tmo" in c:
                    obs.append((c["tmo"], False))
            files[(q, kind, "pat")] = wfile(f"pat_{q}_{kind}{tag}", km_samples(obs, rng, NS))
            # talk by block. jan-feb ran short, impatient callers hung up before an agent
            # got to them and they were the short calls, so talk times of calls that queued
            # are skewed long. calls put straight through to a free agent are an unselected
            # sample of who rings.
            bt = collections.defaultdict(list)
            for c in sub:
                if "talk" in c and (NAIVE_TALK or c["hold"] - c["ring"] <= 5):
                    bt[block(c["end"] - c["talk"])].append(c["talk"])
            # monday: one factor for the whole day (ratio of monday to tue-fri talk, averaged
            # over the three parts of the day) applied to the larger tue-fri samples. six
            # mondays are too few to estimate each monday block on its own, and a yes/no
            # "is monday different" test flips under resampling.
            parts = ("am", "pm", "eve")
            rs = [np.mean(bt["mon_" + p]) / np.mean(bt["wk_" + p]) for p in parts
                  if len(bt["mon_" + p]) > 50 and len(bt["wk_" + p]) > 50]
            rbar = float(np.mean(rs)) if rs else 1.0
            for p in parts:
                bt["mon_" + p] = list(np.array(bt["wk_" + p], float) * rbar)
            for b, v in list(bt.items()):
                if not v:
                    continue
                v = np.array(v, float)
                files[(q, kind, "talk", b)] = wfile(f"talk_{q}_{kind}_{b}{tag}", rng.choice(v, NS) + rng.uniform(-0.5, 0.5, NS))
        rings = np.array([c["ring"] for c in cs if "ring" in c], float)
        files[(q, "ring")] = wfile(f"ring_{q}{tag}", np.maximum(0, rng.choice(rings, NS) + rng.uniform(-0.5, 0.5, NS)))
        spans = np.array([c["span"] for c in cs if c.get("span") is not None], float)
        span = rng.choice(spans, NS)
        files[(q, "after")] = wfile(f"after_{q}{tag}", np.where(span > 0, np.maximum(WRAP_NEW[q], span), WRAP_NEW[q]))
    bill = [c for c in calls if c["q"] == "billing" and "talk" in c]
    pxfer = sum(1 for c in bill if c.get("xfer") == "moving") / len(bill)
    return files, pxfer


def occ(files):
    return sum(np.loadtxt(f).mean() for f in files[1:])


def run(streams, nlo, nhi, timeout, seed):
    spec = [f"seed {seed}", f"narr {NARR}", "warm 0.05", f"timeout {timeout}",
            f"slt {SLT}", f"ghost {GHOST}", f"nrange {nlo} {nhi}"]
    for rate, fs in streams:
        spec.append("stream %.9f %s %s %s %s" % ((rate,) + tuple(fs)))
    fd, sp = tempfile.mkstemp(dir=TMP, suffix=".spec")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(spec) + "\n")
    res = subprocess.run([QSIM, sp], capture_output=True, text=True, check=True).stdout
    os.unlink(sp)
    return [tuple(float(x) for x in l.split()) for l in res.split("\n") if l.strip()]


def size(streams, load, timeout, seed):
    nlo, nhi = max(1, int(load * 0.85) - 2), int(load + 4 * math.sqrt(load) + 8)
    while True:
        rows = run(streams, nlo, nhi, timeout, seed)
        ok = [r for r in rows if r[1] >= SL_T and r[2] <= AB_T]
        if ok and (rows[0][1] < SL_T or rows[0][2] > AB_T or nlo == 1):
            return int(ok[0][0]), ok[0][3]
        if not ok:
            nhi += 10
        else:
            nlo = max(1, nlo - 5)


def job(args):
    files, pxfer, d, start, lam, sseed = args
    h = int(start[:2])
    b = blk(d, h)
    seed = d.toordinal() * 1000 + h * 2 + (1 if start.endswith("30") else 0) + sseed * 7919
    out = {}
    fb = (files[("billing", "fresh", "pat")], files[("billing", "ring")],
          files[("billing", "fresh", "talk", b)], files[("billing", "after")])
    rb = lam["billing"] / 1800
    out["billing"], ansb = size([(rb, fb)], rb * occ(fb), TIMEOUT["billing"], seed)
    ff = (files[("faults", "fresh", "pat")], files[("faults", "ring")],
          files[("faults", "fresh", "talk", b)], files[("faults", "after")])
    rf = lam["faults"] / 1800
    out["faults"], _ = size([(rf, ff)], rf * occ(ff), TIMEOUT["faults"], seed + 1)
    fm = (files[("moving", "fresh", "pat")], files[("moving", "ring")],
          files[("moving", "fresh", "talk", b)], files[("moving", "after")])
    xb = b if ("moving", "xfer_in", "talk", b) in files else "wk_pm"
    fx = (files[("moving", "xfer_in", "pat")], files[("moving", "ring")],
          files[("moving", "xfer_in", "talk", xb)], files[("moving", "after")])
    rm = lam["moving"] / 1800
    rx = rb * ansb * pxfer
    out["moving"], _ = size([(rm, fm), (rx, fx)], rm * occ(fm) + rx * occ(fx), TIMEOUT["moving"], seed + 2)
    return d, start, out


def load_calls(qlog):
    calls, agent_ev = parse(qlog)
    attach_after_call(calls, agent_ev)
    return list(calls.values())


def read_forecast(fc):
    lam = collections.defaultdict(dict)
    order = []
    with open(fc) as f:
        for r in csv.DictReader(f):
            k = (r["date"], r["interval_start"])
            if k not in lam:
                order.append(k)
            lam[k][r["queue"]] = float(r["calls"])
    return lam, order


def plan(calls, lam, order, model_seed=7, sim_seed=0, tag=""):
    files, pxfer = build_models(calls, model_seed, tag)
    jobs = [(files, pxfer, dt.date.fromisoformat(d), s, lam[(d, s)], sim_seed) for d, s in order]
    with ProcessPoolExecutor(os.cpu_count() or 2) as ex:
        res = list(ex.map(job, jobs))
    return res, pxfer


def write_plan(res, outp):
    with open(outp, "w") as f:
        f.write("date,interval_start,queue,seats\n")
        for d, s, o in res:
            for q in ("billing", "moving", "faults"):
                f.write(f"{d.isoformat()},{s},{q},{o[q]}\n")


def main():
    qlog, fc, _, outp = sys.argv[1:5]
    calls = load_calls(qlog)
    lam, order = read_forecast(fc)
    res, pxfer = plan(calls, lam, order)
    write_plan(res, outp)
    print("pxfer", round(pxfer, 4), "rows", 3 * len(res))


if __name__ == "__main__":
    main()
