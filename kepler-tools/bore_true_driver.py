#!/usr/bin/env python3
"""Submit bore-true and then run the validation loop, surviving the queue cap.

Parallel sessions on this account race for the five validation slots, so a
one-shot "wait for a slot then hand off" gives up the moment it loses the race.
This keeps trying: run kepler_run.py loop, and if it dies because the account
is already at five Validating records, back off and run it again.

Never deletes anybody else's record to make room.
"""

import json
import os
import subprocess
import sys
import time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
API = os.path.join(ROOT, "kepler-tools", "kepler_api.py")
RUN = os.path.join(ROOT, "kepler-tools", "kepler_run.py")
NAME = "bore-true"
CAP = 5
DEADLINE = time.time() + 12 * 3600
POLL = 150


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def listing():
    try:
        out = subprocess.run([sys.executable, API, "list"], cwd=ROOT,
                             capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except Exception:
        return None


def state():
    """(n_validating, my_record_or_None)"""
    rows = listing()
    if rows is None:
        return None, None
    mine = [r for r in rows if r.get("taskName") == NAME
            and not r.get("deletedAt")]
    live = [r for r in mine if r.get("status") in
            ("Validating", "Needs Review", "Approved")]
    return len([r for r in rows if r.get("status") == "Validating"]), \
        (live[-1] if live else None)


def main():
    while time.time() < DEADLINE:
        n, mine = state()
        if n is None:
            log("list failed, retrying")
            time.sleep(60)
            continue
        if mine is not None:
            log("%s is in flight already: %s %s"
                % (NAME, mine.get("id"), mine.get("status")))
            # hand the watching over to the loop so a verdict failure is caught
            rc = subprocess.call(
                [sys.executable, RUN, "watch", mine.get("id")], cwd=ROOT)
            log("watch exited %s" % rc)
            return rc
        if n >= CAP:
            log("queue full (%d of %d), waiting" % (n, CAP))
            time.sleep(POLL)
            continue

        log("slot looks free (%d of %d), running the submit loop" % (n, CAP))
        rc = subprocess.call(
            [sys.executable, RUN, "loop",
             "--zip", os.path.join(ROOT, "tasks/bore-true/bore-true.zip"),
             "--name", NAME,
             "--category", "Media",
             "--labels", "Music",
             "--src", os.path.join(ROOT, "task-src/bore-true"),
             "--interval", "30"], cwd=ROOT)
        if rc == 0:
            log("submit loop finished clean")
            return 0
        # lost the race, or an infra flake.  check whether we actually landed.
        n2, mine2 = state()
        if mine2 is not None:
            log("record exists after all: %s %s"
                % (mine2.get("id"), mine2.get("status")))
            continue
        log("loop exited %s with no record, backing off" % rc)
        time.sleep(POLL)

    log("gave up after 12 hours")
    return 1


if __name__ == "__main__":
    sys.exit(main())
