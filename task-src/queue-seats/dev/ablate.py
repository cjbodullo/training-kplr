"""plan the week under one misreading of the world and count intervals outside the sealed band.
usage: python3 ablate.py truth.json variant [variant...]"""
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import truth as T
import world as W

VARIANT = None
_orig_samples = T.samples


def var_samples(q, d, h, kind, wrap):
    v = VARIANT
    if v == "old_faults_wrap" and q == "faults":
        wrap = W.WRAP_HIST["faults"]
    pat, rg, tk, af = _orig_samples(q, d, h, kind, wrap)
    tag = f"{v}_{q}_{kind}_{wrap}_{W.block(d, h)}_{int(d.weekday() == 0)}"
    rng = np.random.default_rng(5)
    if v == "no_ring":
        rg = T.wfile(f"zero_ring", np.zeros(10))
    if v == "wrap_only":
        af = T.wfile(f"wraponly_{wrap}", np.full(10, float(wrap)))
    if v == "additive_acw":
        has, delay, length = W.acw(np.random.default_rng(37 + len(q)), q, T.NS)
        af = T.wfile(f"addacw_{q}_{wrap}", wrap + np.where(has, delay + length, 0.0))
    if v == "flat_talk":
        if q == "billing":
            m = 0.88 * 362 + 0.12 * 70
        else:
            m = {"moving": 570, "faults": 315}[q] if kind != "xfer_in" else 470
        sig = W.TALK_SIG[q]
        t = W.lognorm_mean(rng, m, sig, T.NS)
        tk = T.wfile(f"flat_{q}_{kind}", t)
    if v == "no_xfer_legs" and q == "billing":
        tk = T.wfile(f"noleg_{d.weekday()==0}_{W.block(d,h)}", W.talk(rng, q, d, h, T.NS))
    if v == "erlang_c":
        pat = T.wfile("inf_pat", np.full(10, 1e9))
    if v == "naive_patience":
        p = np.loadtxt(pat)
        pat = T.wfile(f"naivepat_{q}_{kind}", rng.exponential(np.mean(p[p < 120]), T.NS))
    if v == "pooled_moving_patience" and q == "moving":
        p1 = W.patience(np.random.default_rng(1), "moving", T.NS // 2, "fresh")
        p2 = W.patience(np.random.default_rng(2), "moving", T.NS // 2, "xfer_in")
        pat = T.wfile("pooled_mov_pat", np.concatenate([p1, p2]))
    return pat, rg, tk, af


def solve(args):
    global VARIANT
    VARIANT = args[-1]
    T.samples = var_samples
    if VARIANT == "no_ghost":
        W.GHOST = 0
    if VARIANT == "no_xfer":
        W.TRANSFER_P = 0.0
    return T.solve_interval(args[:-1])


def main():
    tr = json.load(open(sys.argv[1]))
    band = {(r["date"], r["start"], r["queue"]): r for r in tr}
    for v in sys.argv[2:]:
        jobs = [j + (v,) for j in T.plan_intervals()]
        with ProcessPoolExecutor(8) as ex:
            res = list(ex.map(solve, jobs))
        bad = {"billing": 0, "moving": 0, "faults": 0}
        under = over = 0
        for d, t, o in res:
            for q in W.QUEUES:
                b = band[(d, t, q)]
                n = o[q]["nstar"]
                if n < b["lo"]:
                    bad[q] += 1; under += 1
                elif n > b["hi"]:
                    bad[q] += 1; over += 1
        print(f"{v:24s} out={sum(bad.values()):4d} under={under:4d} over={over:4d} {bad}", flush=True)


if __name__ == "__main__":
    main()
