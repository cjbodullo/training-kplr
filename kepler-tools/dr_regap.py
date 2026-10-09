#!/usr/bin/env python3
"""Resubmit desk-recall after a full backoff behind its deleted predecessor."""
import json, subprocess, sys, time
ROOT = "/home/osboxes/Downloads/afterquery_kepler"
API = ROOT + "/kepler-tools/kepler_api.py"
RUN = ROOT + "/kepler-tools/kepler_run.py"
GAP = 3000            # 50 minutes behind the delete, per the recorded remedy

print("armed, sleeping %ds behind the delete" % GAP, flush=True)
time.sleep(GAP)

for attempt in range(40):
    try:
        rows = json.loads(subprocess.run([sys.executable, API, "list"],
                          capture_output=True, text=True, timeout=180).stdout)
    except Exception as exc:
        print("list failed: %s" % exc, flush=True); time.sleep(180); continue
    busy = [t.get("taskName") for t in rows if t.get("status") == "Validating"]
    if any(t.get("taskName") == "desk-recall" and not t.get("deletedAt")
           for t in rows):
        print("desk-recall already live, stopping", flush=True); break
    print("%d validating: %s" % (len(busy), busy), flush=True)
    if len(busy) < 5:
        r = subprocess.run([sys.executable, RUN, "submit", "--zip",
                            ROOT + "/tasks/desk-recall/desk-recall.zip",
                            "--name", "desk-recall", "--category", "Media",
                            "--labels", "Music"],
                           capture_output=True, text=True, timeout=1200)
        print(r.stdout[-3000:], r.stderr[-1500:], flush=True)
        break
    time.sleep(240)
