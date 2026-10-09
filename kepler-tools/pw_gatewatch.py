#!/usr/bin/env python3
"""Hold poll-weight until the similarity stage is passing again for anybody.

Four submissions in fifteen minutes blocked at similarity, from three sessions
and two categories, with the last pass twenty two hours old.  That is the
queue, not the bundle, so the record is left standing and the zip is held.

This watches listMine.  As soon as ANY submission created after the block gets
through similarity, it deletes the failed poll-weight record and resubmits the
identical zip.  If nothing passes inside the window it stops and says so, and
the failed record is still there to look at.
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILED = "sTOLVXOSpamqIqsSpCQ7"
ZIP = os.path.join(ROOT, "tasks/poll-weight/poll-weight.zip")
SRC = os.path.join(ROOT, "task-src/poll-weight")
INTERVAL = 600
WINDOW = 6 * 3600


def listmine():
    out = subprocess.run([sys.executable, os.path.join(HERE, "kepler_api.py"),
                          "list"], capture_output=True, text=True).stdout
    i = out.find("[")
    return json.loads(out[i:]) if i >= 0 else []


def main():
    started = time.time()
    seen_at_start = {r["id"] for r in listmine()}
    print("watching from %d records" % len(seen_at_start), flush=True)
    while time.time() - started < WINDOW:
        time.sleep(INTERVAL)
        try:
            rows = listmine()
        except Exception as exc:                       # noqa: BLE001
            print("list failed: %s" % exc, flush=True)
            continue
        fresh = [r for r in rows if r["id"] not in seen_at_start]
        passed = []
        for r in fresh:
            sim = (r.get("pipeline") or {}).get("similarity") or {}
            if sim and not sim.get("blocked"):
                passed.append(r.get("taskName"))
        print("%s  fresh=%d  through similarity=%s"
              % (time.strftime("%H:%M"), len(fresh), passed or "none"), flush=True)
        if passed:
            print("similarity is passing again (%s).  deleting %s and "
                  "resubmitting the identical zip." % (passed[0], FAILED),
                  flush=True)
            subprocess.run([sys.executable, os.path.join(HERE, "kepler_api.py"),
                            "delete", FAILED])
            time.sleep(30)
            subprocess.run([sys.executable, os.path.join(HERE, "kepler_run.py"),
                            "loop", "--zip", ZIP, "--name", "poll-weight",
                            "--category", "Operations", "--labels", "Compliance",
                            "--src", SRC, "--similarity-retries", "0",
                            "--max-rounds", "1", "--interval", "20"])
            return 0
    print("nothing passed similarity inside the window.  the failed record is "
          "still standing and the zip is unchanged.", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
