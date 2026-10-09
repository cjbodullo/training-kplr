"""Watch the gate's health, then submit and poll.

Six Operations tasks from five sessions blocked at similarity between 16:06 and
16:50 on unrelated subjects. That is the infra signature, so this waits for a
healthy signal (any submission of this account clearing similarity after now)
before spending the re-cut bundle, and holds the record if it blocks anyway.
"""
import sys, time, json, datetime, subprocess
sys.path.insert(0, 'kepler-tools')
import kepler_api as K

ZIP = "tasks/single-view/single-view.zip"
STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "runAudit"]
START = time.time()


def now():
    return datetime.datetime.now().strftime("%H:%M")


def rows():
    r = K.list_mine()
    r.sort(key=lambda x: x.get("createdAt") or 0, reverse=True)
    return r


def sim(r):
    return ((r.get("pipeline") or {}).get("similarity") or {}).get("status")


# --- phase 1: wait for a similarity pass on anything submitted after 16:00 ---
CUT = START - 60 * 60
healthy = False
for _ in range(60):
    try:
        rs = rows()
    except Exception as e:
        print(now(), "list error", e, flush=True); time.sleep(180); continue
    recent = [r for r in rs if (r.get("createdAt") or 0) / 1000.0 > CUT]
    passed = [r["taskName"] for r in recent if sim(r) == "passed"]
    blocked = [r["taskName"] for r in recent if sim(r) == "failed"]
    pending = [r["taskName"] for r in recent if sim(r) is None
               and r.get("status") in ("Validating", "Queued", "Running")]
    print(now(), "since 16:00 -> passed %s | blocked %s | pending %s"
          % (passed, blocked, pending), flush=True)
    if passed:
        healthy = True
        print(now(), "gate is answering; %s cleared similarity" % passed, flush=True)
        break
    if not pending:
        print(now(), "nothing in flight to read the gate from; going anyway",
              flush=True)
        break
    time.sleep(240)

# --- phase 2: submit on a gap -----------------------------------------------
for _ in range(40):
    rs = rows()
    age = time.time() - (rs[0]["createdAt"] / 1000.0) if rs else 1e9
    if age >= 12 * 60:
        break
    print(now(), "last submission %.1f min ago, holding" % (age / 60.0), flush=True)
    time.sleep(180)

sid = None
for attempt in range(5):
    r = subprocess.run([sys.executable, "kepler-tools/kepler_run.py", "submit",
                        "--zip", ZIP, "--name", "single-view",
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

# --- phase 3: poll every five minutes ---------------------------------------
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
            print((p["failureReason"])[:6000], flush=True)
        for s in ("qualityCheck", "cheatProbe", "easinessProbe",
                  "difficultyProbe", "runAudit"):
            d = p.get(s) or {}
            if d.get("status"):
                print("---", s, json.dumps(d)[:2000], flush=True)
        break
