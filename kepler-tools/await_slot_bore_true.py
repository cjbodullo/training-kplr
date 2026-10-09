#!/usr/bin/env python3
"""Wait for a free validation slot, then hand bore-true to the submit loop.

The cap is 5 concurrent Validating records across the whole account, and the
five in flight belong to other sessions, so this waits rather than deleting
anybody's work.
"""

import json
import os
import subprocess
import sys
import time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
API = os.path.join(ROOT, "kepler-tools", "kepler_api.py")
RUN = os.path.join(ROOT, "kepler-tools", "kepler_run.py")
CAP = 5
NAME = "bore-true"


def validating():
    out = subprocess.run([sys.executable, API, "list"], cwd=ROOT,
                         capture_output=True, text=True, timeout=240)
    if out.returncode != 0:
        return None, out.stderr[-400:]
    try:
        rows = json.loads(out.stdout)
    except Exception as exc:
        return None, "unparsable list: %s" % exc
    return [r for r in rows if r.get("status") == "Validating"], None


def main():
    deadline = time.time() + 8 * 3600
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
            if any(r.get("taskName") == NAME for r in rows):
                print("%s is already in flight, nothing to do" % NAME, flush=True)
                return 0
            if len(rows) < CAP:
                print("slot free, submitting", flush=True)
                return subprocess.call(
                    [sys.executable, RUN, "loop",
                     "--zip", os.path.join(ROOT, "tasks/bore-true/bore-true.zip"),
                     "--name", NAME,
                     "--category", "Media",
                     "--labels", "Music",
                     "--src", os.path.join(ROOT, "task-src/bore-true"),
                     "--interval", "30"], cwd=ROOT)
        time.sleep(240)
    print("gave up waiting for a slot", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
