"""Ablation battery: how many graded scenarios each plausible wrong reading corrupts."""

from __future__ import annotations

import sys

from model import Engine
from topology import build

READINGS = [
    ("attempts_as_total", "envoy/istio/urllib3/polly/haproxy/go numbers as total"),
    ("attempts_as_retries", "grpc/tenacity/resilience4j/nginx numbers read as retries"),
    ("no_mesh", "sidecar retry layer ignored entirely"),
    ("mesh_everywhere", "mesh retries applied without checking sidecar injection"),
    ("ignore_vs_match", "VirtualService uri match ignored"),
    ("retry_any_5xx", "every layer assumed to retry on any 5xx"),
    ("propagate_all", "deadline assumed to propagate on every hop"),
    ("propagate_none", "deadline assumed never to propagate"),
    ("parallel_as_sequential", "fan-out services read as sequential"),
    ("no_fanout", "per-call fan-out multiplicity ignored"),
    ("hedge_once", "hedging read as a single attempt"),
    ("no_overall", "overall timeouts not truncating retries"),
    ("nginx_post_retries", "edge idempotence gate ignored"),
    ("haproxy_503", "haproxy all-retryable-errors read as covering 503"),
    ("budget_divides", "mesh retry budget applied to a single cold request"),
]


def answer(flags=None):
    svcs, scens = build(flags)
    eng = Engine(svcs)
    return {sc.key: eng.evaluate(sc) for sc in scens}


def main():
    truth = answer()
    n = len(truth)
    print(f"{n} scenarios; total requests {sum(sum(v['requests'].values()) for v in truth.values())}")
    print(f"{'reading':38s} {'bad':>4s} {'counts':>7s} {'elapsed':>8s} {'outcome':>8s}   silent")
    worst = 0
    for flag, label in READINGS:
        got = answer({flag: True})
        bad = c = e = o = 0
        for k in truth:
            diff = False
            if got[k]["requests"] != truth[k]["requests"]:
                c += 1
                diff = True
            if got[k]["elapsed_ms"] != truth[k]["elapsed_ms"]:
                e += 1
                diff = True
            if got[k]["client_outcome"] != truth[k]["client_outcome"]:
                o += 1
                diff = True
            bad += diff
        worst = max(worst, bad)
        print(f"{label:38s} {bad:4d} {c:7d} {e:8d} {o:8d}   yes")
    return truth


if __name__ == "__main__":
    main()
