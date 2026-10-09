"""run the reference planner many times to measure how far a correct method moves.
usage: python3 spread.py QUEUE_LOG FORECAST QSIM OUTDIR kind:seed [kind:seed ...]
kind = seed (fresh model + simulator seeds on the data as is)
       boot (day block bootstrap of the history, stratified by weekday, plus fresh seeds)"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "..", "solution"), os.path.join(HERE, "..", "solution")]
import plan as P  # noqa: E402


def main():
    qlog, fc, qsim, outdir = sys.argv[1:5]
    P.QSIM = qsim
    os.makedirs(outdir, exist_ok=True)
    calls = P.load_calls(qlog)
    lam, order = P.read_forecast(fc)
    for spec in sys.argv[5:]:
        kind, s = spec.split(":")
        s = int(s)
        out = os.path.join(outdir, f"{kind}_{s}.csv")
        if os.path.exists(out):
            continue
        data = calls if kind == "seed" else P.resample_days(calls, np.random.default_rng(1000 + s))
        res, _ = P.plan(data, lam, order, model_seed=100 + s, sim_seed=s, tag=f"_{kind}{s}")
        P.write_plan(res, out + ".tmp")
        os.replace(out + ".tmp", out)
        print("done", spec, flush=True)


if __name__ == "__main__":
    main()
