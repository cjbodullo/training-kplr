#!/usr/bin/env python3
"""Wait for a free validation slot, then submit desk-recall once and watch."""
import json
import subprocess
import sys
import time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
API = ROOT + "/kepler-tools/kepler_api.py"


def listing():
    out = subprocess.run([sys.executable, API, "list"], capture_output=True,
                         text=True, timeout=180)
    return json.loads(out.stdout)


while True:
    try:
        rows = listing()
    except Exception as exc:
        print("list failed: %s" % exc, flush=True)
        time.sleep(120)
        continue
    busy = [t for t in rows if t.get("status") == "Validating"]
    mine = [t for t in rows if t.get("taskName") == "desk-recall"]
    if mine:
        print("desk-recall already submitted: %s" % [t.get("status")
                                                     for t in mine], flush=True)
        break
    print("%s validating: %s" % (len(busy), [t.get("taskName") for t in busy]),
          flush=True)
    if len(busy) < 5:
        r = subprocess.run(
            [sys.executable, ROOT + "/kepler-tools/kepler_run.py", "submit",
             "--zip", ROOT + "/tasks/desk-recall/desk-recall.zip",
             "--name", "desk-recall", "--category", "Media",
             "--labels", "Music"],
            capture_output=True, text=True, timeout=1200)
        print(r.stdout[-4000:], flush=True)
        print(r.stderr[-2000:], flush=True)
        break
    time.sleep(180)
