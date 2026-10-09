"""Hold dock-window until a real gap has passed since its last send, then
submit once and poll.

v1 -> v2 was 3h 17m and cleared similarity. v3 at 1 min and v4 at 31 min both
blocked against v1/v2, which are in the index for good. So this waits out the
gap that has actually worked rather than retrying into it, and it checks the
gate is answering before spending the send.
"""
import sys, time, json, datetime, subprocess
sys.path.insert(0, 'kepler-tools')
import kepler_api as K

ZIP, NAME = "tasks/dock-window/dock-window.zip", "dock-window"
# v4 went in at 01:55.  Hold until the gap since then is a little over the
# 3h 17m that cleared similarity for v2, counted from when this starts.
START = time.time()
HOLD = 105 * 60
STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "runAudit"]


def now():
    return datetime.datetime.now().strftime("%H:%M")


def sim(r):
    return ((r.get("pipeline") or {}).get("similarity") or {}).get("status")


while True:
    left = (START + HOLD) - time.time()
    if left <= 0:
        break
    print(now(), "holding %.0f more minutes" % (left / 60.0), flush=True)
    time.sleep(min(900, left))

# the gate has to be answering before the send is worth spending
for _ in range(24):
    try:
        rs = K.list_mine()
    except Exception as e:
        print(now(), "list error", e, flush=True); time.sleep(300); continue
    rs.sort(key=lambda x: x.get("createdAt") or 0, reverse=True)
    recent = rs[:8]
    passed = [r["taskName"] for r in recent if sim(r) == "passed"]
    age = (time.time() - rs[0]["createdAt"] / 1000.0) / 60.0 if rs else 1e9
    print(now(), "recent similarity passes %s | last send %.0f min ago"
          % (passed[:4], age), flush=True)
    if passed and age >= 12:
        break
    time.sleep(300)

sid = None
for _ in range(5):
    r = subprocess.run([sys.executable, "kepler-tools/kepler_run.py", "submit",
                        "--zip", ZIP, "--name", NAME, "--category", "Operations",
                        "--labels", "Supply chain"], capture_output=True, text=True)
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
                print("---", s, json.dumps(d)[:2000], flush=True)
        break
