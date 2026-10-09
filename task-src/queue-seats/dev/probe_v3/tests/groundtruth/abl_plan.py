"""the reference planner with exactly one misreading switched on, writes a plan csv.
usage: python3 abl_plan.py QUEUE_LOG FORECAST QSIM OUTDIR variant [variant ...]
variants:
  naive_talk      talk times from every answered call (ignores who hung up before an agent got to them)
  erlang_c        nobody abandons (infinite patience)
  naive_patience  exponential patience with the mean wait of abandoned calls
  wrap_only       after call time = wrapuptime, ACW pauses ignored
  additive_acw    after call time = wrapuptime + ACW span
  old_faults_wrap faults wrapuptime left at 20
  flat_talk       one talk distribution per queue (no time of day / Monday blocks)
  no_xfer_legs    billing talk without the short legs of transferred calls
  no_xfer         no transfer load into moving
  no_ghost        sub 10 s abandons counted in service level and abandon rate"""
import collections
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "..", "solution"), os.path.join(HERE, "..", "solution")]
import plan as P  # noqa: E402

V = None
_build = P.build_models


def build(calls, seed=7, tag=""):
    tag = tag + "_" + V
    if V == "naive_talk":
        P.NAIVE_TALK = True
    if V == "old_faults_wrap":
        P.WRAP_NEW["faults"] = 20
    true_calls = calls
    if V == "no_xfer_legs":
        # transferred billing calls drop out of the talk sample only
        calls = [{k: v for k, v in c.items() if k != "talk"} if c["q"] == "billing" and c.get("xfer") else c
                 for c in calls]
    files, pxfer = _build(calls, seed, tag)
    rng = np.random.default_rng(3)
    if V == "no_xfer_legs":
        bill = [c for c in true_calls if c["q"] == "billing" and "talk" in c]
        pxfer = sum(1 for c in bill if c.get("xfer") == "moving") / len(bill)
    if V == "no_xfer":
        pxfer = 0.0
    for k, f in list(files.items()):
        if V == "erlang_c" and k[-1] == "pat":
            files[k] = P.wfile(f"inf_{k[0]}_{k[1]}{tag}", np.full(10, 1e9))
        if V == "naive_patience" and k[-1] == "pat":
            q, kind = k[0], k[1]
            ab = [c["aband"] for c in calls if c["q"] == q and "aband" in c and c["xfer_in"] == (kind == "xfer_in")]
            files[k] = P.wfile(f"npat_{q}_{kind}{tag}", rng.exponential(np.mean(ab), P.NS))
        if V in ("wrap_only", "additive_acw") and k[-1] == "after":
            q = k[0]
            if V == "wrap_only":
                files[k] = P.wfile(f"wo_{q}{tag}", np.full(10, float(P.WRAP_NEW[q])))
            else:
                sp = np.array([c["span"] for c in calls if c["q"] == q and c.get("span") is not None], float)
                files[k] = P.wfile(f"add_{q}{tag}", P.WRAP_NEW[q] + rng.choice(sp, P.NS))
    if V == "flat_talk":
        pooled = collections.defaultdict(list)
        for k, f in files.items():
            if len(k) > 2 and k[2] == "talk":
                pooled[(k[0], k[1])].append(np.loadtxt(f))
        for k in list(files):
            if len(k) > 2 and k[2] == "talk":
                v = np.concatenate(pooled[(k[0], k[1])])
                files[k] = P.wfile(f"flat_{k[0]}_{k[1]}{tag}", rng.choice(v, P.NS))
    return files, pxfer


def main():
    global V
    qlog, fc, qsim, outdir = sys.argv[1:5]
    P.QSIM = qsim
    os.makedirs(outdir, exist_ok=True)
    calls = P.load_calls(qlog)
    lam, order = P.read_forecast(fc)
    P.build_models = build
    for v in sys.argv[5:]:
        if os.path.exists(os.path.join(outdir, f"{v}.csv")):
            continue
        V = v
        P.NAIVE_TALK = False
        P.WRAP_NEW["faults"] = 60
        P.GHOST = 0 if v == "no_ghost" else 10
        res, _ = P.plan(calls, lam, order)
        P.write_plan(res, os.path.join(outdir, f"{v}.csv.tmp"))
        os.replace(os.path.join(outdir, f"{v}.csv.tmp"), os.path.join(outdir, f"{v}.csv"))
        print("done", v, flush=True)


if __name__ == "__main__":
    main()
