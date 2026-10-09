#!/usr/bin/env python3
"""Poll a submission until it reaches a terminal state.

    python3 poll_submission.py <submissionId> [intervalSeconds]

Prints one compact stage line per tick, plus per-trial detail for the probe
stages, and stops as soon as the submission leaves "Validating".
"""

import json
import subprocess
import sys
import time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
API = ROOT + "/kepler-tools/kepler_api.py"
ORDER = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
         "cheatProbe", "easinessProbe", "difficultyProbe", "runAudit"]


def stamp():
    return time.strftime("%H:%M:%S")


def fetch(sub):
    out = subprocess.run([sys.executable, API, "status", sub], cwd=ROOT,
                         capture_output=True, text=True, timeout=150)
    return json.loads(out.stdout)


def main():
    sub = sys.argv[1]
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    for _ in range(200):
        try:
            rec = fetch(sub)
        except Exception as exc:
            print("[%s] poll failed: %r" % (stamp(), exc), flush=True)
            time.sleep(interval)
            continue

        pipe = rec.get("pipeline") or {}
        bits = []
        for name in ORDER:
            st = pipe.get(name)
            if isinstance(st, dict):
                bits.append("%s:%s" % (name, st.get("stage") or st.get("status")))
        status = rec.get("status")
        print("[%s] %s | %s" % (stamp(), status, "  ".join(bits)), flush=True)

        for name in ("easinessProbe", "difficultyProbe"):
            st = pipe.get(name)
            if isinstance(st, dict) and st.get("trials"):
                trials = st["trials"]
                print("    %s passCount=%s of %d  %s"
                      % (name, st.get("passCount"), len(trials),
                         [(t.get("reward"), round(t.get("durationSeconds") or 0))
                          for t in trials]), flush=True)

        if status and status != "Validating":
            print("TERMINAL: %s" % status, flush=True)
            if rec.get("rejection"):
                print(json.dumps(rec["rejection"], indent=1)[:1500], flush=True)
            return 0
        time.sleep(interval)
    return 1


if __name__ == "__main__":
    sys.exit(main())
