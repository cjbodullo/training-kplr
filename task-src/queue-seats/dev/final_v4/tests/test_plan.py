"""grade the seat plan for w/c 2027-03-01 against sealed seat bands.

nstar is the smallest seat count meeting 80% answered within 20 s and at most 5% abandoned
after 10 s under the call centre's true behaviour (the behaviour that generated the jan-feb
queue_log) with the march queue config, from long steady state runs of every half hour.
the accepted band is nstar - 2 .. nstar + 1 widened by every answer of 16 re-runs of the
reference method with fresh seeds and day bootstraps of the history, and checked on 8 more
held out re-runs. see groundtruth/README.md."""
import csv
import json
import re
from pathlib import Path

import pytest

PLAN = Path("/app/plan.csv")
BANDS = json.loads(Path("/tests/bands.json").read_text())
KEYS = {(b["date"], b["start"], b["queue"]): b for b in BANDS}


def load():
    assert PLAN.is_file(), "/app/plan.csv is missing"
    text = PLAN.read_text()
    rows = list(csv.reader(text.splitlines()))
    assert rows, "plan.csv is empty"
    assert [c.strip() for c in rows[0]] == ["date", "interval_start", "queue", "seats"], rows[0]
    plan = {}
    for i, r in enumerate(rows[1:], start=2):
        if not r or all(not c.strip() for c in r):
            continue
        assert len(r) == 4, f"line {i}: expected 4 fields, got {r}"
        d, s, q, n = (c.strip() for c in r)
        assert re.fullmatch(r"2027-03-0[1-6]", d), f"line {i}: bad date {d!r}"
        assert re.fullmatch(r"\d\d:[03]0", s), f"line {i}: bad interval_start {s!r}"
        assert re.fullmatch(r"\d+", n), f"line {i}: seats must be a whole number, got {n!r}"
        k = (d, s, q)
        assert k in KEYS, f"line {i}: {k} is not an open half hour of a queue"
        assert k not in plan, f"line {i}: duplicate row for {k}"
        plan[k] = int(n)
    return plan


@pytest.fixture(scope="module")
def plan():
    return load()


def test_every_half_hour_present(plan):
    missing = sorted(set(KEYS) - set(plan))
    assert not missing, f"{len(missing)} half hours missing, e.g. {missing[:5]}"


@pytest.mark.parametrize("queue", ["billing", "moving", "faults"])
def test_seats_meet_target_without_overstaffing(plan, queue):
    under, over = [], []
    for k, b in KEYS.items():
        if b["queue"] != queue or k not in plan:
            continue
        n = plan[k]
        if n < b["lo"]:
            under.append((k[0], k[1], n, b["nstar"]))
        elif n > b["hi"]:
            over.append((k[0], k[1], n, b["nstar"]))
    msg = f"{queue}: {len(under)} half hours under staffed, {len(over)} over staffed"
    assert not under and not over, msg + f"; under {under[:4]} over {over[:4]}"
