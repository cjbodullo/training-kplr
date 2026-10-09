#!/usr/bin/env python3
"""Poll the cutover-audit submission every 60s, print a compact stage line on change."""
import json, subprocess, sys, time

STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "difficultyProbe", "runAudit"]
last = None
deadline = time.time() + 3 * 3600
while time.time() < deadline:
    try:
        out = subprocess.run(["python3", "kepler-tools/kepler_api.py", "list"],
                             capture_output=True, text=True, timeout=120).stdout
        rows = [t for t in json.loads(out) if t.get("taskName") == "cutover-audit"]
    except Exception as exc:
        print("%s poll error: %s" % (time.strftime("%H:%M:%S"), exc), flush=True)
        time.sleep(60); continue
    if not rows:
        print("%s not listed yet" % time.strftime("%H:%M:%S"), flush=True)
        time.sleep(30); continue
    t = rows[0]
    p = t.get("pipeline") or {}
    line = "%s %s | stage=%s | %s" % (
        t.get("id"), t.get("status"), p.get("stage"),
        " ".join("%s=%s" % (s, (p.get(s) or {}).get("status", "-"))
                 for s in STAGES if isinstance(p.get(s), dict)))
    if line != last:
        print("%s %s" % (time.strftime("%H:%M:%S"), line), flush=True)
        last = line
    st = (t.get("status") or "").lower()
    if "failed" in st or "passed" in st or "review" in st or "approved" in st:
        print("TERMINAL: %s" % t.get("status"), flush=True)
        print(json.dumps(p, indent=1), flush=True)
        break
    time.sleep(60)
