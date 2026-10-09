#!/usr/bin/env python3
"""Poll one submission every 300s until terminal; print stage transitions."""
import json, os, subprocess, sys, time

SID = sys.argv[1]
ROOT = "/home/osboxes/Downloads/afterquery_kepler"
MAX = int(sys.argv[2]) if len(sys.argv) > 2 else 96

def get():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "kepler-tools", "kepler_api.py"),
                          "status", SID], capture_output=True, text=True, timeout=180)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return None

last = None
for i in range(MAX):
    rec = get()
    if rec is None:
        print("[%d] no record (token?)" % i, flush=True)
        time.sleep(300); continue
    pipe = rec.get("pipeline") or {}
    stage = pipe.get("stage")
    status = rec.get("status")
    stages = []
    for name in ("structure", "ai_check", "similarity", "oracle_nop", "quality_check",
                 "cheat_probe", "easiness_probe", "difficulty_probe", "run_audit",
                 "trajectory_review"):
        blob = pipe.get(name)
        if isinstance(blob, dict):
            v = blob.get("verdict") or blob.get("band") or blob.get("passed")
            if blob.get("error"): v = "ERROR:%s" % str(blob["error"])[:40]
            stages.append("%s=%s" % (name, v))
    line = "%s | %s | %s" % (status, stage, " ".join(stages))
    if line != last:
        print("[%s] %s" % (time.strftime("%H:%M:%S"), line), flush=True)
        last = line
    if status in ("Needs Review", "Approved", "Validation Failed", "Rejected"):
        print("TERMINAL:", status, flush=True)
        print(json.dumps(pipe, indent=1)[:6000], flush=True)
        break
    time.sleep(300)
