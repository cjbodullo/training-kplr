import sys, time, json, datetime, subprocess
sys.path.insert(0, 'kepler-tools')
import kepler_api as K

ZIP = "tasks/single-view/single-view.zip"
GAP = 15 * 60   # no submission of this account inside this window


def stamp():
    return datetime.datetime.now().strftime("%H:%M")


def newest_age():
    rows = K.list_mine()
    if not rows:
        return 1e9, []
    rows.sort(key=lambda r: r.get("createdAt") or 0, reverse=True)
    age = time.time() - (rows[0]["createdAt"] / 1000.0)
    live = [r["taskName"] for r in rows
            if r.get("status") in ("Validating", "Queued", "Running")]
    return age, live


for _ in range(40):
    try:
        age, live = newest_age()
    except Exception as e:
        print(stamp(), "list error", e, flush=True); time.sleep(120); continue
    print(stamp(), "last submission %.1f min ago; live: %s" % (age / 60.0, live),
          flush=True)
    if age >= GAP:
        break
    time.sleep(180)

print(stamp(), "submitting on a clean gap", flush=True)
for attempt in range(4):
    r = subprocess.run([sys.executable, "kepler-tools/kepler_run.py", "submit",
                        "--zip", ZIP, "--name", "single-view",
                        "--category", "Operations", "--labels", "Marketing"],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print(stamp(), out[-400:], flush=True)
    if "submissionId:" in out:
        sid = out.split("submissionId:")[1].split("|")[0].strip()
        break
    time.sleep(30)
else:
    sys.exit(1)

STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "runAudit"]
last = None
for _ in range(220):
    time.sleep(300)
    try:
        rec = K.get(sid)
    except Exception as e:
        print(stamp(), "poll error", e, flush=True); continue
    p = rec.get("pipeline") or {}
    line = " ".join("%s=%s" % (s, (p.get(s) or {}).get("status", "-"))
                    for s in STAGES if s in p)
    if line != last:
        print(stamp(), rec.get("status"), "|", line, flush=True)
        last = line
    if rec.get("status") not in ("Validating", "Queued", "Running"):
        print(stamp(), "TERMINAL", rec.get("status"), "at",
              p.get("failedStage"), flush=True)
        if p.get("failureReason"):
            print(p["failureReason"][:6000], flush=True)
        for s in STAGES:
            d = p.get(s) or {}
            if d.get("status") and s in ("easinessProbe", "difficultyProbe",
                                         "cheatProbe", "qualityCheck"):
                print("---", s, json.dumps(d)[:1500], flush=True)
        break
