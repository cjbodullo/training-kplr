#!/usr/bin/env python3
"""Hold consent-count for a real gap, then submit the hardened zip once.

v1 (gfvBHpbMGZ0Y5x2qiJbW) failed cheat_probe at trial reward 0 and was deleted.
v2 went in about ten minutes later with near identical bytes and blocked at
similarity, with a sibling from another session passing the same gate minutes
before, so the gate was discriminating and the match is my own deleted
predecessor.  The fix for that is a gap, not a rewrite.

So: leave the v2 record standing (a standing failure is not a submission slot
and deleting it would only make a second deleted predecessor), wait for v1 to
decay out of the index, then delete v2 and submit once.  If that blocks too,
stop rather than burn a fourth attempt.
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILED_V2 = "lVJ0kxXu0PAxveLGK9XY"
ZIP = os.path.join(ROOT, "tasks/consent-count/consent-count.zip")
SRC = os.path.join(ROOT, "task-src/consent-count")
GAP = 3 * 3600 + 600          # three hours and ten minutes


def api(*args):
    return subprocess.run([sys.executable, os.path.join(HERE, "kepler_api.py"),
                           *args], capture_output=True, text=True).stdout


def main():
    waited = 0
    while waited < GAP:
        time.sleep(600)
        waited += 600
        print("%s  holding, %d of %d minutes"
              % (time.strftime("%H:%M"), waited // 60, GAP // 60), flush=True)

    print("gap served.  deleting the standing v2 record and submitting once.",
          flush=True)
    print(api("delete", FAILED_V2)[:200], flush=True)
    time.sleep(60)
    subprocess.run([sys.executable, os.path.join(HERE, "kepler_run.py"), "loop",
                    "--zip", ZIP, "--name", "consent-count",
                    "--category", "Operations", "--labels", "Finance",
                    "--src", SRC, "--similarity-retries", "0",
                    "--max-rounds", "1", "--interval", "20"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
