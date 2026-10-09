import sys, time, json
sys.path.insert(0,'/home/osboxes/Downloads/afterquery_kepler/kepler-tools')
import kepler_api as K
sid = "AskHeQcSyhcmjcxgGjnY"
last = ""
for _ in range(600):
    try:
        d = K.get(sid)
    except Exception as e:
        print("poll error", e, flush=True); time.sleep(30); continue
    p = d.get("pipeline") or {}
    line = "status=%s stage=%s" % (d.get("status"), p.get("stage"))
    for k in ("structure","aiCheck","similarity","oracleNop","qualityCheck",
              "cheatProbe","easinessProbe","difficultyProbe","trajectoryReview"):
        v = p.get(k)
        if isinstance(v, dict):
            line += " | %s=%s" % (k, v.get("status"))
    if line != last:
        print(time.strftime("%H:%M:%S"), line, flush=True)
        last = line
    if d.get("status") in ("Needs Review","Approved","Validation Failed","Rejected"):
        print("FINAL", d.get("status"), "failedStage=", p.get("failedStage"),
              "reason=", p.get("failureReason"), flush=True)
        print(json.dumps({k: p.get(k) for k in
              ("oracleNop","qualityCheck","cheatProbe","easinessProbe",
               "difficultyProbe")}, default=str)[:6000], flush=True)
        break
    time.sleep(60)
