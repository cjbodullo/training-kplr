#!/usr/bin/env python3
"""Poll road-space every 300s until terminal."""
import json, os, subprocess, sys, time
os.chdir("/home/osboxes/Downloads/afterquery_kepler")
SID = "LcYScPogjL1K6BT6vl8i"
for _ in range(120):
    try:
        out = subprocess.run([sys.executable, "kepler-tools/kepler_api.py",
                              "status", SID], capture_output=True, text=True,
                             timeout=180)
        d = json.loads(out.stdout)
        p = d.get("pipeline") or {}
        print("%s %s stage=%s failed=%s %s" % (
            time.strftime("%H:%M:%S"), d.get("status"), p.get("stage"),
            p.get("failedStage"), (p.get("failureReason") or "")[:90]),
            flush=True)
        if d.get("status") not in ("Validating", "Queued", "Pending"):
            break
    except Exception as exc:
        print("poll error: %s" % exc, flush=True)
    time.sleep(300)
