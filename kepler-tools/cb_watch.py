#!/usr/bin/env python3
"""Resilient watcher for one submission.

kepler_run.py's watch() dies on a transient network error -- a 60s curl (28)
timeout took the crash-bucket poller down twice, each time leaving a perfectly
healthy submission running server-side with nobody looking at it. This polls the
same API but treats every network fault, token blip and parse failure as
retryable, so the only thing that stops it is a real verdict.

    python3 kepler-tools/cb_watch.py <submissionId> [--interval 30] [--out FILE]

Never deletes anything. Never resubmits. Read only.
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(HERE, "kepler_api.py")
STAGES = ("structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "trajectoryReview")
TERMINAL = ("Approved", "Rejected", "Needs Review", "Validation Failed")


def say(msg, out):
    line = "%s  %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    if out:
        with open(out, "a") as fh:
            fh.write(line + "\n")


def poll(sid):
    """Return the task dict, or None on any transient problem."""
    try:
        p = subprocess.run([sys.executable, API, "status", sid],
                           capture_output=True, text=True, timeout=180)
    except Exception:
        return None
    s = p.stdout or ""
    starts = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    if not starts:
        return None
    try:
        d = json.loads(s[min(starts):])
    except Exception:
        return None
    return d[0] if isinstance(d, list) else d


def summarise(pipe):
    bits = []
    for k in STAGES:
        v = pipe.get(k)
        if isinstance(v, dict) and v.get("status"):
            bits.append("%s:%s" % (k, v["status"]))
    return "  ".join(bits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission_id")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    say("watching %s (read only)" % a.submission_id, a.out)
    last = None
    misses = 0
    while True:
        d = poll(a.submission_id)
        if d is None:
            misses += 1
            if misses in (1, 5, 20) or misses % 40 == 0:
                say("poll failed (%d in a row) -- retrying, the pipeline is "
                    "unaffected" % misses, a.out)
            time.sleep(min(300, a.interval * (1 + misses // 5)))
            continue
        misses = 0

        pipe = d.get("pipeline") or {}
        line = summarise(pipe)
        if line != last:
            say(line, a.out)
            last = line

        status = d.get("status")
        if status in TERMINAL:
            say("=== %s ===" % status, a.out)
            fs, fk = pipe.get("failedStage"), pipe.get("failureKind")
            if fs:
                say("failedStage=%s kind=%s" % (fs, fk), a.out)
                if pipe.get("failureReason"):
                    say("reason: %s" % pipe["failureReason"], a.out)
            for k in ("easinessProbe", "difficultyProbe"):
                v = pipe.get(k)
                if isinstance(v, dict) and v.get("trials"):
                    say("%s band=%s rewards=%s" % (
                        k, v.get("band"),
                        [t.get("reward") for t in v["trials"]]), a.out)
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
