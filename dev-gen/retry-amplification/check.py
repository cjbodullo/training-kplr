"""Fairness proof: the reference, reading only shipped files, must equal the truth."""
import json, os, sys
SOL = os.path.abspath("../../task-src/retry-amplification/solution")
APP = os.path.abspath("../../task-src/retry-amplification/environment/app")
sys.path.insert(0, SOL)
import parse_config, parse_traces, run as runner
parse_config.APP = APP
parse_traces.APP = APP
runner.APP = APP
runner.main()
got = json.load(open(os.path.join(APP, "analysis.json")))["scenarios"]
truth = json.load(open("../../task-src/retry-amplification/tests/truth.json"))["scenarios"]
bad = 0
for k in sorted(truth):
    if got.get(k) != truth[k]:
        bad += 1
        if bad <= 4:
            print("MISMATCH", k)
            t, g = truth[k], got.get(k, {})
            print("  truth", t["elapsed_ms"], t["client_outcome"], t["requests"])
            print("  got  ", g.get("elapsed_ms"), g.get("client_outcome"), g.get("requests"))
print(f"{len(truth) - bad}/{len(truth)} scenarios match")
os.remove(os.path.join(APP, "analysis.json"))
sys.exit(1 if bad else 0)
