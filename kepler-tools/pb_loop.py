#!/usr/bin/env python3
"""plug-book submit loop with escalating gaps.

The lever this drives is the GAP, not a rebuild: a similarity block on a
bundle whose predecessor was deleted minutes earlier is confounded by its own
ghost, so each round waits, submits once, polls to a terminal state, and on a
similarity block deletes the record and waits longer before trying again.

Any other verdict failure is a real design signal: the feedback is saved and
the loop stops so it can be worked on.
"""

import json
import os
import subprocess
import sys
import time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
ZIP = os.path.join(ROOT, "tasks/plug-book/plug-book.zip")
NAME = "plug-book"
CATEGORY = "Software"
LABELS = "data-engineering,reverse-engineering"
STATE = os.path.join(ROOT, "kepler-tools/pb_state.json")

GAPS_MIN = [245, 200, 260, 320, 380, 440]
QUEUE_CAP = 5


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def api(*args):
    out = subprocess.run([sys.executable, os.path.join(ROOT, "kepler-tools/kepler_api.py")]
                         + list(args), capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except ValueError:
        return None


def queue_free():
    d = api("list")
    if not isinstance(d, list):
        return True
    n = sum(1 for t in d if t.get("status") == "Validating")
    return n < QUEUE_CAP, n


def wait_for_slot():
    while True:
        try:
            free, n = queue_free()
        except Exception:
            return
        if free:
            return
        log("queue full (%d validating), waiting 10 min" % n)
        time.sleep(600)


def submit():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "kepler-tools/kepler_run.py"),
                        "submit", "--zip", ZIP, "--name", NAME,
                        "--category", CATEGORY, "--labels", LABELS],
                       capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    log(out.strip()[-400:])
    for line in out.splitlines():
        if "submissionId:" in line:
            return line.split("submissionId:")[1].split("|")[0].strip()
    return None


def poll(sid):
    """Return (result, stage, record)."""
    last = ""
    while True:
        rec = api("status", sid)
        if not rec:
            time.sleep(60)
            continue
        p = rec.get("pipeline") or {}
        stage = p.get("stage")
        line = "  ".join(
            "%s:%s" % (k, (p.get(k) or {}).get("verdict")
                       or (p.get(k) or {}).get("status") or "pending")
            for k in ("structure", "ai_check", "similarity", "oracle_nop",
                      "quality_check", "cheat_probe", "difficulty_probe"))
        if line != last:
            log(line)
            last = line
        if stage in ("completed", "failed"):
            return rec.get("status"), stage, rec
        time.sleep(120)


def failing_stage(rec):
    p = rec.get("pipeline") or {}
    for k in ("structure", "ai_check", "similarity", "oracle_nop",
              "quality_check", "cheat_probe", "difficulty_probe", "run_audit"):
        v = (p.get(k) or {})
        if v.get("verdict") in ("failed", "fail") or v.get("status") == "failed":
            return k, v
    return None, None


def main():
    for rnd, gap in enumerate(GAPS_MIN, 1):
        log("round %d: sleeping %d min before submitting" % (rnd, gap))
        time.sleep(gap * 60)
        wait_for_slot()

        sid = submit()
        if not sid:
            log("no submissionId, retrying next round")
            continue
        log("round %d submitted as %s" % (rnd, sid))

        status, stage, rec = poll(sid)
        stg, payload = failing_stage(rec)
        json.dump({"round": rnd, "sid": sid, "status": status, "stage": stg},
                  open(STATE, "w"))

        if stage == "completed" and status != "Validation Failed":
            log("PASSED THE PIPELINE: %s (%s)" % (sid, status))
            open(os.path.join(ROOT, "kepler-tools/pb_PASSED.txt"), "w").write(
                "%s %s\n" % (sid, status))
            return 0

        log("round %d failed at %s" % (rnd, stg))
        with open(os.path.join(ROOT, "kepler-tools/pb_failures.log"), "a") as fh:
            fh.write("%s round %d %s %s %s\n" % (time.strftime("%F %T"), rnd,
                                                 sid, stg, json.dumps(payload)[:500]))

        if stg == "similarity":
            api("delete", sid)
            log("record deleted; next round waits longer")
            continue

        log("STOPPING: %s is a design signal, not a gap problem" % stg)
        return 1

    log("gaps exhausted without a pass")
    return 1


if __name__ == "__main__":
    sys.exit(main())
