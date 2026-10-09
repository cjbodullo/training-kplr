import json, subprocess, sys, time
SID = sys.argv[1]
OUT = "/tmp/claude-1000/-home-osboxes-Downloads-afterquery-kepler/10773dce-8b95-4d69-8247-c2d4e9472ef3/scratchpad/gv_live.json"
STAGES = ("structure","aiCheck","similarity","oracleNop","qualityCheck",
          "cheatProbe","easinessProbe","difficultyProbe","trajectoryReview")
last = None
for _ in range(400):
    try:
        r = subprocess.run(["python3","kepler-tools/kepler_api.py","status",SID],
                           capture_output=True, text=True, timeout=180)
        d = json.loads(r.stdout)
    except Exception as exc:
        time.sleep(60); continue
    open(OUT,"w").write(json.dumps(d))
    p = d.get("pipeline") or {}
    line = "%s | %s" % (d.get("status"), " ".join(
        "%s=%s" % (s, (p.get(s) or {}).get("status") if isinstance(p.get(s),dict) else p.get(s))
        for s in STAGES if p.get(s) is not None))
    if line != last:
        print(time.strftime("%H:%M:%S"), line, flush=True)
        last = line
    if d.get("status") not in ("Validating", "Queued", None):
        print("FINAL:", d.get("status"), "failedStage:", p.get("failedStage"),
              "reason:", p.get("failureReason"), flush=True)
        break
    time.sleep(60)
