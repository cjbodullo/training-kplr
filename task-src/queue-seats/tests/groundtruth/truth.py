"""compute the sealed seat bands for the plan week from the TRUE world.
usage: python3 truth.py OUT.json [variant]
variant lets dev ablations swap one piece of the world for a naive reading."""
import datetime as dt
import json
import math
import os
import subprocess
import sys
import tempfile
import zlib
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import world as W

QSIM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qsim")
NS = 400000
NARR = int(os.environ.get("NARR", "300000"))
TMP = tempfile.mkdtemp(prefix="qs_truth_")


def wfile(name, arr):
    p = os.path.join(TMP, name)
    if not os.path.exists(p):
        tmp = p + ".%d" % os.getpid()
        np.savetxt(tmp, arr, fmt="%.3f")
        os.replace(tmp, p)
    return p


def samples(q, d, h, kind, wrap):
    """sample files for one stream, keyed so they are reused"""
    key = f"{q}_{W.block(d, h)}_{int(d.weekday() == 0)}_{kind}_{wrap}"
    rng = np.random.default_rng(zlib.crc32(key.encode()))
    pat = wfile(f"pat_{q}_{kind}", W.patience(np.random.default_rng(11 + len(q) + len(kind)), q, NS, kind))
    rg = wfile(f"ring_{q}", W.ring(np.random.default_rng(23 + len(q)), q, NS))
    if q == "billing":
        t = W.talk(rng, q, d, h, NS, kind)
        leg = W.talk(rng, q, d, h, NS, "xfer_leg")
        x = rng.random(NS) < W.TRANSFER_P
        t = np.where(x, leg, t)
    elif kind == "xfer_in":
        t = W.talk(rng, q, d, h, NS, "xfer_in")
    else:
        t = W.talk(rng, q, d, h, NS, kind)
    tk = wfile(f"talk_{key}", t)
    af = wfile(f"after_{q}_{wrap}", W.after(np.random.default_rng(37 + len(q)), q, NS, wrap))
    return pat, rg, tk, af


def run(streams, nlo, nhi, timeout, seed):
    spec = [f"seed {seed}", f"narr {NARR}", "warm 0.05", f"timeout {timeout}",
            f"slt {W.SLT}", f"ghost {W.GHOST}", f"nrange {nlo} {nhi}"]
    for rate, files in streams:
        spec.append("stream %.9f %s %s %s %s" % ((rate,) + tuple(files)))
    fd, sp = tempfile.mkstemp(dir=TMP, suffix=".spec")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(spec) + "\n")
    out = subprocess.run([QSIM, sp], capture_output=True, text=True, check=True).stdout
    os.unlink(sp)
    rows = []
    for line in out.split("\n"):
        if line.strip():
            v = line.split()
            ns = len(streams)
            rows.append((int(v[0]), float(v[1]), float(v[2]), float(v[3]),
                         [float(x) for x in v[4 + ns:4 + 2 * ns]]))
    return rows


def band(streams, load, timeout, seed):
    nlo = max(1, int(load * 0.85) - 2)
    nhi = int(load + 4 * math.sqrt(load) + 8)
    while True:
        rows = run(streams, nlo, nhi, timeout, seed)
        ok = [r for r in rows if r[1] >= W.SL_TARGET and r[2] <= W.AB_TARGET]
        if ok and (ok[0][0] > nlo or nlo == 1):
            break
        if not ok:
            nhi += 10
        else:
            nlo = max(1, nlo - 5)
    nstar = ok[0][0]
    by = {r[0]: r for r in rows}
    st, below = by[nstar], by.get(nstar - 1)
    # one seat either side is accepted only where the true figure sits close to a target
    lo = nstar - 1 if below and below[1] >= W.SL_TARGET - 0.02 and below[2] <= W.AB_TARGET + 0.01 else nstar
    hi = nstar + 1 if st[1] < W.SL_TARGET + 0.02 or st[2] > W.AB_TARGET - 0.01 else nstar
    return {"nstar": nstar, "lo": lo, "hi": hi, "sl": st[1], "ab": st[2], "ans": st[3], "lost": st[4],
            "sl_below": below[1] if below else 0.0, "ab_below": below[2] if below else 1.0}


def mean_occ(files):
    return sum(np.loadtxt(f).mean() for f in files[1:])


def typed(q, d, h, rate):
    """fresh callers of one queue as two streams, quick and complex"""
    qs = W.QUICK_SHARE[q]
    st = [(rate * qs, samples(q, d, h, "quick", W.WRAP_MARCH[q])),
          (rate * (1 - qs), samples(q, d, h, "complex", W.WRAP_MARCH[q]))]
    return st, sum(r * mean_occ(f) for r, f in st)


def band_redial(q, fresh, extra, timeout, seed):
    """fresh = [(rate, files)] for quick, complex; extra = other streams (transfers in).
    repeat attempts of each kind arrive at rate * L * p / (1 - decay * p * L), L the share of
    that kind lost after 10 s or more at the planned seats; solved by fixed point."""
    p, dec = W.REDIAL_P[q], W.REDIAL_DECAY
    red = [0.0, 0.0]
    res = None
    for _ in range(4):
        streams = fresh + [(red[i], fresh[i][1]) for i in range(2) if red[i] > 0] + extra
        load = sum(r * mean_occ(f) for r, f in streams)
        res = band(streams, load, timeout, seed)
        lost = res["lost"]
        new = [fresh[i][0] * lost[i] * p / (1 - dec * p * lost[i]) for i in range(2)]
        if all(abs(new[i] - red[i]) <= 1e-4 * max(fresh[i][0], 1e-9) for i in range(2)):
            break
        red = new
    res["redial_rate_30"] = sum(red) * 1800
    return res


def solve_interval(args):
    d, h, m, lam = args
    out = {}
    seed = (d.toordinal() * 100 + h * 2 + m // 30) * 7 + 1
    # billing first, its answered share drives transfers into moving
    sb, _ = typed("billing", d, h, lam["billing"] / 1800.0)
    out["billing"] = band_redial("billing", sb, [], 0, seed)
    sf, _ = typed("faults", d, h, lam["faults"] / 1800.0)
    out["faults"] = band_redial("faults", sf, [], W.FAULTS_TIMEOUT, seed + 1)
    sm, _ = typed("moving", d, h, lam["moving"] / 1800.0)
    fx = samples("moving", d, h, "xfer_in", W.WRAP_MARCH["moving"])
    rb_total = lam["billing"] / 1800.0 + out["billing"]["redial_rate_30"] / 1800.0
    rx = rb_total * out["billing"]["ans"] * W.TRANSFER_P
    out["moving"] = band_redial("moving", sm, [(rx, fx)], 0, seed + 2)
    out["moving"]["xfer_rate_30"] = rx * 1800
    return (d.isoformat(), "%02d:%02d" % (h, m), out)


def plan_intervals():
    jobs = []
    for k in range(6):
        d = W.PLAN_START + dt.timedelta(days=k)
        ivs = W.intervals(d)
        lam = {q: W.expected_calls(q, d, W.PLAN_CAMPAIGN) for q in W.QUEUES}
        for i, (h, m) in enumerate(ivs):
            jobs.append((d, h, m, {q: lam[q][i] for q in W.QUEUES}))
    return jobs


def main():
    out = sys.argv[1]
    jobs = plan_intervals()
    # prebuild shared sample files serially (avoid write races)
    for d, h, m, lam in jobs:
        for q in W.QUEUES:
            for k in ("quick", "complex"):
                samples(q, d, h, k, W.WRAP_MARCH[q])
        samples("moving", d, h, "xfer_in", W.WRAP_MARCH["moving"])
    with ProcessPoolExecutor(int(os.environ.get("JOBS", "8"))) as ex:
        res = list(ex.map(solve_interval, jobs))
    rows = []
    for (d, t, o), (_, _, _, lam) in zip(res, jobs):
        for q in W.QUEUES:
            r = dict(o[q])
            r.update({"date": d, "start": t, "queue": q, "forecast": round(lam[q], 1)})
            rows.append(r)
    json.dump(rows, open(out, "w"), indent=0)
    print("intervals", len(rows), "tmp", TMP)


if __name__ == "__main__":
    main()
