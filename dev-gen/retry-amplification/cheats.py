"""Emit attempted answers that must all score 0 through the real verifier."""
import copy, json, os
from model import Engine
from topology import build

OUT = os.path.abspath("../../task-src/retry-amplification/cheat")
os.makedirs(OUT, exist_ok=True)

def answer(flags=None):
    svcs, scens = build(flags)
    eng = Engine(svcs)
    return {s.key: eng.evaluate(s) for s in scens}

truth = answer()

def dump(name, scenarios):
    with open(os.path.join(OUT, name), "w") as fh:
        json.dump({"scenarios": scenarios}, fh, indent=1, sort_keys=True)
        fh.write("\n")

for flag, name in [
    ("no_mesh", "analysis_sidecar_layer_ignored.json"),
    ("mesh_everywhere", "analysis_mesh_without_injection.json"),
    ("attempts_as_total", "analysis_retries_read_as_attempts.json"),
    ("attempts_as_retries", "analysis_attempts_read_as_retries.json"),
    ("retry_any_5xx", "analysis_every_layer_retries_5xx.json"),
    ("propagate_all", "analysis_deadline_always_propagated.json"),
    ("propagate_none", "analysis_deadline_never_propagated.json"),
    ("no_fanout", "analysis_fanout_ignored.json"),
    ("parallel_as_sequential", "analysis_fanout_service_sequential.json"),
    ("hedge_once", "analysis_hedging_counted_once.json"),
    ("nginx_post_retries", "analysis_idempotence_gate_ignored.json"),
    ("budget_divides", "analysis_retry_budget_applied.json"),
    ("ignore_vs_match", "analysis_route_match_ignored.json"),
]:
    dump(name, answer({flag: True}))

# the whole estate, one request each
flat = {k: {"requests": {s: 1 for s in v["requests"]},
            "elapsed_ms": v["elapsed_ms"], "client_outcome": v["client_outcome"]}
        for k, v in truth.items()}
dump("analysis_one_request_each.json", flat)

# correct everywhere but a single count, and a single elapsed
off = copy.deepcopy(truth)
key = sorted(off)[0]
first = sorted(off[key]["requests"])[0]
off[key]["requests"][first] += 1
dump("analysis_one_count_off_by_one.json", off)

slow = copy.deepcopy(truth)
slow[sorted(slow)[3]]["elapsed_ms"] += 25
dump("analysis_one_elapsed_off.json", slow)

drop = copy.deepcopy(truth)
victim = max(truth, key=lambda k: len(truth[k]["requests"]))
gone = sorted(drop[victim]["requests"])[-1]
del drop[victim]["requests"][gone]
dump("analysis_one_service_missing.json", drop)

extra = copy.deepcopy(truth)
extra[sorted(extra)[5]]["requests"]["catalog-reindex-job"] = 1
dump("analysis_batch_job_counted.json", extra)

outcome = copy.deepcopy(truth)
for v in outcome.values():
    if v["client_outcome"] == "client_timeout":
        v["client_outcome"] = "504"
dump("analysis_timeout_called_504.json", outcome)

print(len(os.listdir(OUT)), "cheat files")
