#!/usr/bin/env python3
"""kepler_run.py loop semantics, attached to a submission that is already in flight.

Same behaviour as cmd_loop after its first submit, minus the duplicate submission:

  - poll the pipeline, surviving DNS drops and stale tokens
  - infra flake  -> delete the dead task and resubmit the same zip, keep going
                    (does not count against rounds)
  - verdict fail -> save <src>/last_failure.md and append <src>/failures.log,
                    then stop for redesign (no rebuild hook can fix a difficulty
                    verdict), optionally deleting the failed task
  - passed       -> report and exit 0

    python3 kepler-tools/loop_attach.py <submissionId> --zip Z --name N \
        --category C --labels a,b --src DIR [--delete-on-fail] [--max-rounds 5]
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kepler_api as api

STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "trajectoryReview"]
TERMINAL_OK = ("Approved", "Needs Review")


def state(pipeline, key):
    v = pipeline.get(key)
    if v is None:
        return "pending"
    if isinstance(v, dict):
        return v.get("status") or "running"
    return str(v)


def watch(sid, interval=20):
    """Poll until terminal. -> (result, stage, reason, pipeline) with result in
    passed | failed | infra."""
    last = None
    misses = 0
    while True:
        try:
            d = api.get(sid)
            misses = 0
        except Exception as e:
            misses += 1
            if misses % 10 == 1:
                print("  poll error (%s), retrying" % str(e)[:90], flush=True)
            time.sleep(interval)
            continue

        p = d.get("pipeline") or {}
        ep, dp = p.get("easinessProbe") or {}, p.get("difficultyProbe") or {}
        line = "  ".join("%s:%s" % (k, state(p, k)) for k in STAGES)
        line += " | easiness %s/%s | difficulty %s %s" % (
            ep.get("passCount"), ep.get("maxPasses"), dp.get("passCount"), dp.get("band") or "")
        if line != last:
            print(line, flush=True)
            last = line

        if p.get("stage") == "failed":
            kind = p.get("failureKind")
            return ("infra" if kind == "infra" else "failed",
                    p.get("failedStage"), p.get("failureReason"), p)
        if d.get("status") in TERMINAL_OK:
            return ("passed", None, d.get("status"), p)
        time.sleep(interval)


def save_failure(src, sid, stage, reason, pipeline):
    if not src:
        return
    src = Path(src)
    body = ("# last failure\n\n- submissionId: %s\n- stage: %s\n- result: failed\n\n"
            "## reason\n%s\n\n## raw pipeline\n```json\n%s\n```\n"
            % (sid, stage, reason, json.dumps(pipeline, indent=2)[:200000]))
    try:
        (src / "last_failure.md").write_text(body)
        with open(src / "failures.log", "a") as fh:
            fh.write("%s\t%s\t%s\n" % (sid, stage, str(reason)[:300]))
        print("  feedback saved -> %s" % (src / "last_failure.md"), flush=True)
    except Exception as e:
        print("  (could not save feedback: %s)" % e, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission_id")
    ap.add_argument("--zip", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--src", default=None)
    ap.add_argument("--delete-on-fail", action="store_true", dest="delete_on_fail")
    ap.add_argument("--max-rounds", type=int, default=5)
    ap.add_argument("--interval", type=int, default=20)
    args = ap.parse_args()

    sid = args.submission_id
    # an infra flake is the harness failing, not the task: it gets its own
    # ceiling and must not eat a verdict round.
    rnd = 0
    infra_retries = 0
    max_infra_retries = max(12, args.max_rounds * 4)
    while rnd < args.max_rounds:
        rnd += 1
        print("\n=== watching %s (round %d/%d) ===" % (sid, rnd, args.max_rounds), flush=True)
        result, stage, reason, pipeline = watch(sid, args.interval)

        if result == "passed":
            print("\nPASSED automated pipeline (%s). submissionId: %s" % (reason, sid), flush=True)
            print("awaiting human review, nothing more to automate.", flush=True)
            return 0

        if result == "infra":
            infra_retries += 1
            rnd -= 1  # genuinely does not count against the verdict rounds
            print("\ninfra flake at %s; deleting and resubmitting the same zip "
                  "(infra retry %d/%d, verdict round still %d/%d)."
                  % (stage, infra_retries, max_infra_retries, rnd + 1, args.max_rounds),
                  flush=True)
            if infra_retries >= max_infra_retries:
                print("%d infra flakes without a verdict; the harness looks sick. "
                      "Stopping." % max_infra_retries, flush=True)
                return 2
            try:
                api.delete(sid)
            except Exception as e:
                print("  delete failed: %s" % e, flush=True)
            for attempt in range(6):
                try:
                    fin = api.submit(args.zip, args.name, args.category, args.labels.split(","))
                    break
                except Exception as e:
                    print("  resubmit error (%s), retrying" % str(e)[:90], flush=True)
                    time.sleep(30)
            else:
                print("could not resubmit; stopping.", flush=True)
                return 2
            sid = fin.get("submissionId")
            print("resubmitted -> %s | structureOk: %s" % (sid, fin.get("structureOk")), flush=True)
            for f in fin.get("findings", []):
                print("  finding [%s] %s: %s" % (f.get("level"), f.get("code"), f.get("message")),
                      flush=True)
            if not sid:
                return 2
            continue

        print("\nFAILED at %s: %s" % (stage, reason), flush=True)
        save_failure(args.src, sid, stage, reason, pipeline)
        print("no rebuild hook can fix this stage (needs real task redesign).", flush=True)
        if args.delete_on_fail:
            try:
                api.delete(sid)
                print("deleted failed task %s." % sid, flush=True)
            except Exception as e:
                print("  delete failed: %s" % e, flush=True)
        else:
            print("failed task %s left in place for inspection." % sid, flush=True)
        return 1
    print("\nreached max-rounds without a verdict.", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
