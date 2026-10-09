import json, subprocess, sys, time
ID = "CD1fQeIzNZuUPImdSUr3"
STAGES = ["structure","aiCheck","similarity","oracleNop","qualityCheck",
          "cheatProbe","easinessProbe","difficultyProbe","trajectoryReview"]
last = None
for i in range(220):
    try:
        out = subprocess.run([sys.executable,"kepler-tools/kepler_api.py","status",ID],
                             capture_output=True, text=True, timeout=90).stdout
        d = json.loads(out)
    except Exception as e:
        time.sleep(60); continue
    p = d.get("pipeline") or {}
    row = " ".join(f"{s}={(p.get(s) or {}).get('status','-')}" for s in STAGES
                   if p.get(s) is not None)
    line = f"{time.strftime('%H:%M')} {d.get('status')} | {row}"
    if line[6:] != (last or "")[6:]:
        print(line, flush=True)
        last = line
    if d.get("status") not in ("Validating", "Submitted", None):
        print("TERMINAL:", d.get("status"), "failedStage=", p.get("failedStage"),
              "reason=", (p.get("failureReason") or "")[:2000], flush=True)
        break
    time.sleep(60)
