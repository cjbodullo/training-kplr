#!/usr/bin/env python3
"""Wait for a free validation slot, then run the deckle-line submit loop."""
import json, os, subprocess, sys, time
ROOT = "/home/osboxes/Downloads/afterquery_kepler"
os.chdir(ROOT)

def inflight():
    out = subprocess.run([sys.executable, "kepler-tools/kepler_api.py", "list"],
                         capture_output=True, text=True, timeout=180)
    d = json.loads(out.stdout)
    return sum(1 for x in d if x.get("status") in ("Validating", "Queued", "Pending"))

deadline = time.time() + 6 * 3600
while time.time() < deadline:
    try:
        n = inflight()
    except Exception as exc:
        print("list failed: %s" % exc, flush=True)
        time.sleep(300)
        continue
    print("%s in flight %d" % (time.strftime("%H:%M:%S"), n), flush=True)
    if n < 5:
        break
    time.sleep(300)

print("slot free, submitting", flush=True)
subprocess.run([sys.executable, "kepler-tools/kepler_run.py", "loop",
                "--zip", "tasks/deckle-line/deckle-line.zip",
                "--name", "deckle-line",
                "--category", "Media",
                "--labels", "Design",
                "--src", "task-src/deckle-line",
                "--max-rounds", "1"], check=False)
