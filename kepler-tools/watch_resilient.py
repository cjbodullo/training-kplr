#!/usr/bin/env python3
"""Poll one submission until terminal, surviving DNS/token blips.

    python3 kepler-tools/watch_resilient.py <submissionId> [src_dir]

Prints a line whenever any stage changes. On a terminal outcome writes
<src_dir>/last_failure.md (on failure) and prints OUTCOME: ... .
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kepler_api as api

STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "trajectoryReview"]


def state(pipeline, key):
    v = pipeline.get(key)
    if v is None:
        return "pending"
    if isinstance(v, dict):
        return v.get("status") or "running"
    return str(v)


def main():
    sid = sys.argv[1]
    src = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    last = None
    misses = 0
    while True:
        try:
            d = api.get(sid)
            misses = 0
        except Exception as e:
            misses += 1
            if misses % 10 == 1:
                print("poll error (%s), retrying" % str(e)[:80], flush=True)
            time.sleep(20)
            continue

        p = d.get("pipeline") or {}
        line = "  ".join("%s:%s" % (k, state(p, k)) for k in STAGES)
        ep = p.get("easinessProbe") or {}
        dp = p.get("difficultyProbe") or {}
        extra = " | easiness %s/%s | difficulty %s %s" % (
            ep.get("passCount"), ep.get("maxPasses"), dp.get("passCount"), dp.get("band") or "")
        if line + extra != last:
            print(line + extra, flush=True)
            last = line + extra

        if p.get("stage") == "failed":
            reason = p.get("failureReason")
            stage = p.get("failedStage")
            kind = p.get("failureKind")
            print("OUTCOME: failed at %s (kind=%s)\n%s" % (stage, kind, reason), flush=True)
            if src:
                (src / "last_failure.md").write_text(
                    "# %s failed at %s (kind=%s)\n\n%s\n\n## full pipeline\n\n```json\n%s\n```\n"
                    % (sid, stage, kind, reason, json.dumps(p, indent=2)[:200000]))
            return 1
        if d.get("status") in ("Approved", "Needs Review"):
            print("OUTCOME: %s" % d.get("status"), flush=True)
            return 0
        if all(state(p, k) == "passed" for k in STAGES if k in p or k in
               ("structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
                "cheatProbe", "difficultyProbe", "trajectoryReview")):
            print("OUTCOME: automated pipeline passed", flush=True)
            return 0
        time.sleep(20)


if __name__ == "__main__":
    raise SystemExit(main())
