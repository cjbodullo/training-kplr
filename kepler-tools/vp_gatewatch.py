#!/usr/bin/env python3
"""Wait for the similarity gate to come back, then submit volume-post once.

During an outage every submission is wasted and every delete seeds a ghost of
itself in the index.  So instead of retrying on a timer, poll the account for
evidence the gate is healthy again: any task, any session, whose similarity
stage has passed recently.  Only then hand over to the normal loop.
"""
import subprocess
import sys
import time

sys.path.insert(0, "/home/osboxes/Downloads/afterquery_kepler/kepler-tools")
import kepler_api as api

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
POLL = 300
FRESH_MS = 90 * 60 * 1000        # "recently" = the last 90 minutes


def healthy():
    """True if some task cleared similarity in the last FRESH_MS."""
    now = int(time.time() * 1000)
    rows = [r for r in api.list_mine() if isinstance(r, dict)]
    fresh = [r for r in rows
             if r.get("updatedAt") and now - r["updatedAt"] < FRESH_MS]
    passed, failed, last = [], [], []
    for r in fresh:
        try:
            p = api.get(r["id"]).get("pipeline") or {}
        except Exception:
            continue
        sim = p.get("similarity")
        s = sim.get("status") if isinstance(sim, dict) else sim
        ran = (sim or {}).get("ranAt") if isinstance(sim, dict) else None
        if s == "passed":
            passed.append(r.get("taskName"))
            if ran:
                last.append(ran)
        elif s == "failed":
            failed.append("%s(judge=%s)" % (r.get("taskName"),
                                            (sim or {}).get("judge")))
            if ran:
                last.append(ran)
    return passed, failed, len(fresh), (max(last) if last else None)


def main():
    while True:
        try:
            passed, failed, n, last = healthy()
        except Exception as exc:                       # token expiry, network
            print("%s poll failed: %s" % (time.strftime("%H:%M:%S"), exc),
                  flush=True)
            time.sleep(POLL)
            continue
        quiet_min = None
        if last:
            quiet_min = (int(time.time() * 1000) - last) // 60000
        print("%s  fresh=%d  passed=%s  failed=%s  last similarity result %s"
              % (time.strftime("%H:%M:%S"), n, passed or "-", failed or "-",
                 ("%d min ago" % quiet_min) if quiet_min is not None else "none"),
              flush=True)
        # If nobody has exercised the gate for a while, "no pass" is not
        # evidence of an outage any more, it just means nobody is testing it.
        # Probe it ourselves rather than wait forever.
        stale = quiet_min is None or quiet_min >= 40
        if passed or stale:
            why = ("%s cleared similarity" % ", ".join(passed) if passed
                   else "no similarity result on the account for %s minutes, "
                        "probing the gate ourselves"
                        % (quiet_min if quiet_min is not None else "90+"))
            print("submitting: %s" % why, flush=True)
            subprocess.run(
                [sys.executable, "-u", "kepler-tools/kepler_run.py", "loop",
                 "--zip", "tasks/volume-post/volume-post.zip",
                 "--name", "volume-post", "--category", "ML",
                 "--labels", "Data engineering",
                 "--src", "task-src/volume-post",
                 "--similarity-gap", "2400", "--similarity-retries", "2",
                 "--max-rounds", "5", "--interval", "20"],
                cwd=ROOT)
            return
        time.sleep(POLL)


if __name__ == "__main__":
    main()
