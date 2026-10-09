#!/usr/bin/env python3
"""Poll one submission every 5 minutes until it reaches a terminal state."""

import json
import subprocess
import sys
import time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
API = ROOT + "/kepler-tools/kepler_api.py"
SUB = sys.argv[1] if len(sys.argv) > 1 else "pqEOj1WO5GDBI9vXxq3x"

ORDER = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
         "cheatProbe", "easinessProbe", "difficultyProbe", "runAudit"]

for _ in range(72):
    try:
        out = subprocess.run([sys.executable, API, "status", SUB], cwd=ROOT,
                             capture_output=True, text=True, timeout=180)
        rec = json.loads(out.stdout)
    except Exception as exc:
        print("[%s] poll failed: %s" % (time.strftime("%H:%M:%S"), exc),
              flush=True)
        time.sleep(300)
        continue
    pipe = rec.get("pipeline") or {}
    bits = []
    for name in ORDER:
        stage = pipe.get(name)
        if isinstance(stage, dict):
            bits.append("%s:%s" % (name, stage.get("stage")
                                   or stage.get("status")))
    status = rec.get("status")
    print("[%s] %s | %s" % (time.strftime("%H:%M:%S"), status, "  ".join(bits)),
          flush=True)
    if status and status != "Validating":
        for name in ("easinessProbe", "difficultyProbe"):
            stage = pipe.get(name)
            if isinstance(stage, dict) and stage.get("trials"):
                print("%s: passCount=%s of %s" %
                      (name, stage.get("passCount"), len(stage["trials"])),
                      flush=True)
                for t in stage["trials"]:
                    print("   trial %s reward=%s %.0fs $%.2f" %
                          (t.get("trialIndex"), t.get("reward"),
                           t.get("durationSeconds") or 0, t.get("costUsd") or 0),
                          flush=True)
        print("TERMINAL: %s" % status, flush=True)
        if rec.get("rejection"):
            print(json.dumps(rec["rejection"], indent=1)[:1200], flush=True)
        break
    time.sleep(300)
