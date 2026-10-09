#!/usr/bin/env python3
"""Wait for a free validation slot, then hand off to the submit loop."""

import json
import os
import subprocess
import sys
import time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
API = os.path.join(ROOT, "kepler-tools", "kepler_api.py")
RUN = os.path.join(ROOT, "kepler-tools", "kepler_run.py")


def validating():
    out = subprocess.run([sys.executable, API, "list"], cwd=ROOT,
                         capture_output=True, text=True, timeout=180)
    if out.returncode != 0:
        return None, out.stderr[-400:]
    try:
        rows = json.loads(out.stdout)
    except Exception as exc:
        return None, "unparsable list: %s" % exc
    return [r for r in rows if r.get("status") == "Validating"], None


def main():
    deadline = time.time() + 6 * 3600
    while time.time() < deadline:
        rows, err = validating()
        if rows is None:
            print("[%s] list failed: %s" % (time.strftime("%H:%M:%S"), err),
                  flush=True)
        else:
            names = sorted(str(r.get("taskName")) for r in rows)
            print("[%s] %d validating: %s"
                  % (time.strftime("%H:%M:%S"), len(names), ", ".join(names)),
                  flush=True)
            mine = [r for r in rows if r.get("taskName") == "rating-engine"]
            if mine:
                print("rating-engine is already in flight, nothing to do",
                      flush=True)
                return 0
            if len(rows) < 10:
                print("slot free, submitting", flush=True)
                return subprocess.call(
                    [sys.executable, RUN, "loop",
                     "--zip", os.path.join(ROOT, "tasks/rating-engine/rating-engine.zip"),
                     "--name", "rating-engine",
                     "--category", "Software",
                     "--labels", "Systems,Algorithms",
                     "--src", os.path.join(ROOT, "task-src/rating-engine"),
                     "--interval", "30"], cwd=ROOT)
        time.sleep(300)
    print("gave up waiting for a slot", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
