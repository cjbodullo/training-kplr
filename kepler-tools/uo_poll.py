import json, os, re, sys, time
sys.path.insert(0, "kepler-tools")
import kepler_api as k

LOG = "task-src/unwind-order/submit_loop6.log"
STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "easinessProbe", "difficultyProbe", "trajectoryReview", "runAudit"]

def current_id():
    try:
        ids = re.findall(r"submissionId: ([A-Za-z0-9]+)", open(LOG).read())
        return ids[-1] if ids else None
    except OSError:
        return None

last, tracked = None, None
while True:
    sid = current_id()
    if sid is None:
        time.sleep(60); continue
    if sid != tracked:
        print("tracking %s" % sid, flush=True)
        tracked, last = sid, None
    try:
        full = k.get(sid)
    except Exception:
        time.sleep(60); continue
    p = full.get("pipeline") or {}
    cur = {s: (p.get(s) or {}).get("status") for s in STAGES if p.get(s)}
    line = " ".join("%s:%s" % (s, v) for s, v in cur.items() if v)
    st = full.get("status")
    if line != last:
        print("[%s] %s" % (st, line), flush=True)
        last = line
    bad = [s for s, v in cur.items() if v == "failed"]
    if bad:
        for s in bad:
            print("FAILED %s: %s" % (s, json.dumps(p.get(s))[:700]), flush=True)
        print("TERMINAL %s" % st, flush=True)
        break
    if st in ("Needs Review", "Approved"):
        print("TERMINAL %s" % st, flush=True)
        break
    time.sleep(300)
