#!/usr/bin/env python3
"""Resubmit volume-post when ML specifically starts clearing similarity.

Tonight ML went 0 for 9 at the similarity gate while Operations and Media
passed, so gate health has to be measured per category, not globally.  Wait for
an ML task -- anyone's -- to clear, then submit once.
"""
import subprocess
import sys
import time

sys.path.insert(0, "/home/osboxes/Downloads/afterquery_kepler/kepler-tools")
import kepler_api as api

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
POLL = 300
WINDOW = 3 * 3600 * 1000


def scan():
    now = int(time.time() * 1000)
    ml_pass, ml_fail, other_pass = [], [], []
    for r in api.list_mine():
        if not isinstance(r, dict) or not r.get("updatedAt"):
            continue
        if now - r["updatedAt"] > WINDOW:
            continue
        try:
            sim = (api.get(r["id"]).get("pipeline") or {}).get("similarity") or {}
        except Exception:
            continue
        st, ran = sim.get("status"), sim.get("ranAt")
        if not ran:
            continue
        name = r.get("taskName")
        if r.get("category") == "ML":
            (ml_pass if st == "passed" else ml_fail).append((ran, name))
        elif st == "passed":
            other_pass.append((ran, name))
    return ml_pass, ml_fail, other_pass


while True:
    try:
        ml_pass, ml_fail, other_pass = scan()
    except Exception as exc:
        print("%s poll failed: %s" % (time.strftime("%H:%M:%S"), exc), flush=True)
        time.sleep(POLL)
        continue
    print("%s  ML passed=%s  ML failed=%d  non-ML passed=%d"
          % (time.strftime("%H:%M:%S"), [n for _r, n in ml_pass] or "-",
             len(ml_fail), len(other_pass)), flush=True)
    if ml_pass:
        print("ML is clearing again (%s) — submitting once"
              % ", ".join(n for _r, n in ml_pass), flush=True)
        subprocess.run(
            [sys.executable, "-u", "kepler-tools/kepler_run.py", "loop",
             "--zip", "tasks/volume-post/volume-post.zip",
             "--name", "volume-post", "--category", "ML",
             "--labels", "Data engineering", "--src", "task-src/volume-post",
             "--similarity-gap", "3600", "--similarity-retries", "1",
             "--max-rounds", "5", "--interval", "20"],
            cwd=ROOT)
        break
    time.sleep(POLL)
