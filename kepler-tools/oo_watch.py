"""Hold, then resubmit one-owner only on a GENUINE recovery signal.

The corrected probe: a re-submission of a bundle that already cleared
similarity proves nothing. Recovery means a bundle whose name has NOT cleared
similarity before clears it, on a submission created after this watcher starts.
Until then nothing is submitted and the failed record is left standing.
"""
import sys, time, json, datetime, subprocess
sys.path.insert(0, 'kepler-tools')
import kepler_api as K

ZIP, NAME = "tasks/one-owner/one-owner.zip", "one-owner"
STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "runAudit"]
START = time.time()


def now():
    return datetime.datetime.now().strftime("%H:%M")


def sim(r):
    return ((r.get("pipeline") or {}).get("similarity") or {}).get("status")


try:
    baseline = {r["taskName"] for r in K.list_mine() if sim(r) == "passed"}
except Exception as e:
    baseline = set()
print(now(), "names that had already cleared similarity:", sorted(baseline),
      flush=True)

sid = None
for tick in range(300):
    time.sleep(300)
    try:
        rs = K.list_mine()
    except Exception as e:
        print(now(), "list error", e, flush=True); continue
    fresh = [r for r in rs if (r.get("createdAt") or 0) / 1000.0 > START]
    good = [r["taskName"] for r in fresh
            if sim(r) == "passed" and r["taskName"] not in baseline]
    blocked = [r["taskName"] for r in fresh if sim(r) == "failed"]
    if tick % 6 == 0 or good:
        print(now(), "since hold: cleared %s | blocked %s" % (good, blocked),
              flush=True)
    if good:
        print(now(), "RECOVERY: %s cleared similarity first time; resubmitting"
              % good, flush=True)
        for _ in range(5):
            r = subprocess.run([sys.executable, "kepler-tools/kepler_run.py",
                                "submit", "--zip", ZIP, "--name", NAME,
                                "--category", "Operations",
                                "--labels", "Marketing"],
                               capture_output=True, text=True)
            out = (r.stdout + r.stderr).strip()
            print(now(), out[-300:], flush=True)
            if "submissionId:" in out:
                sid = out.split("submissionId:")[1].split("|")[0].strip()
                break
            time.sleep(40)
        break

if not sid:
    print(now(), "no recovery signal seen; nothing submitted", flush=True)
    sys.exit(0)

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
