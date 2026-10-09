import sys, time, json, datetime
sys.path.insert(0, 'kepler-tools')
import kepler_api as K
SID = "ZdHn4p4TITcHr8rEsYoA"
STAGES = ["structure","aiCheck","similarity","oracleNop","qualityCheck",
          "cheatProbe","easinessProbe","difficultyProbe","runAudit"]
last = None
for _ in range(200):
    try:
        r = K.get(SID)
    except Exception as e:
        print("poll error", e, flush=True); time.sleep(300); continue
    p = r.get("pipeline") or {}
    line = " ".join("%s=%s" % (s, (p.get(s) or {}).get("status","-")) for s in STAGES if s in p)
    stamp = datetime.datetime.now().strftime("%H:%M")
    if line != last:
        print(stamp, r.get("status"), "|", line, flush=True)
        if p.get("failedStage"):
            print("FAILED at", p["failedStage"], "kind", p.get("failureKind"), flush=True)
            print((p.get("failureReason") or "")[:4000], flush=True)
        last = line
    if r.get("status") not in ("Validating","Queued","Running"):
        print(stamp, "TERMINAL:", r.get("status"), "failedStage", p.get("failedStage"), flush=True)
        print(json.dumps({k: (v or {}).get("status") for k,v in p.items() if isinstance(v, dict)}, indent=1), flush=True)
        if p.get("failureReason"):
            print(p["failureReason"][:8000], flush=True)
        break
    time.sleep(300)
