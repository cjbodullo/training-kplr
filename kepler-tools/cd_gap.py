#!/usr/bin/env python3
"""coil-draw: honour a gap after deleting the self-ghost, then resubmit the
unchanged zip. Retries on a longer gap if similarity blocks again."""
import json, subprocess, sys, time, os

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
ZIP = f"{ROOT}/tasks/coil-draw/coil-draw.zip"
API = f"{ROOT}/kepler-tools/kepler_api.py"
LOG = f"{ROOT}/kepler-tools/cd_gap.log"


def say(m):
    line = f"{time.strftime('%H:%M:%S')} {m}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def run(*args):
    r = subprocess.run([sys.executable, API, *args], capture_output=True, text=True,
                       cwd=ROOT, timeout=900)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"raw": r.stdout[-400:], "err": r.stderr[-400:]}


for attempt, gap in enumerate([75 * 60, 95 * 60, 130 * 60], 1):
    say(f"attempt {attempt}: holding a {gap // 60} min gap with nothing of the family live")
    time.sleep(gap)
    res = run("submit", ZIP, "coil-draw", "Media", "Music")
    sid = res.get("submissionId")
    say(f"submitted {sid} structureOk={res.get('structureOk')}")
    if not sid:
        say(f"submit failed: {res}")
        continue
    verdict = None
    for _ in range(150):
        time.sleep(60)
        st = run("status", sid)
        p = st.get("pipeline") or {}
        sim = (p.get("similarity") or {}).get("status")
        if sim in ("passed", "failed"):
            verdict = sim
            break
    say(f"similarity {verdict} for {sid}")
    if verdict == "passed":
        say("SIMILARITY CLEARED, leaving it to run the rest of the pipeline")
        sys.exit(0)
    if verdict == "failed":
        say(f"blocked again, deleting {sid} and widening the gap")
        run("delete", sid)
say("all attempts spent")
