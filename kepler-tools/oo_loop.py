"""Submit one-owner on a clean gap, then poll the pipeline every five minutes."""
import sys, time, json, datetime, subprocess
sys.path.insert(0, 'kepler-tools')
import kepler_api as K

ZIP, NAME = "tasks/one-owner/one-owner.zip", "one-owner"
STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "runAudit"]


def now():
    return datetime.datetime.now().strftime("%H:%M")


def rows():
    r = K.list_mine()
    r.sort(key=lambda x: x.get("createdAt") or 0, reverse=True)
    return r


for _ in range(40):
    try:
        rs = rows()
    except Exception as e:
        print(now(), "list error", e, flush=True); time.sleep(120); continue
    age = (time.time() - rs[0]["createdAt"] / 1000.0) / 60.0 if rs else 1e9
    live = [r["taskName"] for r in rs
            if r.get("status") in ("Validating", "Queued", "Running")]
    print(now(), "last submission %.1f min ago; live %s" % (age, live), flush=True)
    if age >= 12:
        break
    time.sleep(180)

sid = None
for _ in range(5):
    r = subprocess.run([sys.executable, "kepler-tools/kepler_run.py", "submit",
                        "--zip", ZIP, "--name", NAME,
                        "--category", "Operations", "--labels", "Marketing"],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print(now(), out[-300:], flush=True)
    if "submissionId:" in out:
        sid = out.split("submissionId:")[1].split("|")[0].strip()
        break
    time.sleep(40)
if not sid:
    sys.exit(1)

last = None
for _ in range(240):
    time.sleep(300)
    try:
        rec = K.get(sid)
    except Exception as e:
        print(now(), "poll error", e, flush=True); continue
    p = rec.get("pipeline") or {}
    line = " ".join("%s=%s" % (s, (p.get(s) or {}).get("status", "-"))
                    for s in STAGES if s in p)
    if line != last:
        print(now(), rec.get("status"), "|", line, flush=True)
        last = line
    if rec.get("status") not in ("Validating", "Queued", "Running"):
        print(now(), "TERMINAL", rec.get("status"), "at", p.get("failedStage"),
              flush=True)
        if p.get("failureReason"):
            print(p["failureReason"][:6000], flush=True)
        for s in ("qualityCheck", "cheatProbe", "easinessProbe",
                  "difficultyProbe", "runAudit"):
            d = p.get(s) or {}
            if d.get("status"):
                print("---", s, json.dumps(d)[:2500], flush=True)
        break
