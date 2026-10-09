import json, subprocess, sys, time
SID = "LX76MJhQaxFG0PsOBUM4"
prev = None
for i in range(200):
    try:
        out = subprocess.run([sys.executable, "kepler-tools/kepler_api.py", "status", SID],
                             capture_output=True, text=True, timeout=120).stdout
        rec = json.loads(out)
    except Exception as exc:
        print(f"[{time.strftime('%H:%M:%S')}] poll error: {exc}", flush=True)
        time.sleep(300); continue
    pipe = rec.get("pipeline") or {}
    stages = pipe.get("stages") or {}
    if isinstance(stages, dict):
        summ = " ".join(f"{k}={v.get('verdict') or v.get('status')}" for k, v in stages.items())
    else:
        summ = str(pipe.get("stage"))
    line = f"[{time.strftime('%H:%M:%S')}] {rec.get('status')} stage={pipe.get('stage')} | {summ}"
    if line != prev:
        print(line, flush=True)
        prev = line
    if rec.get("status") in ("Needs Review", "Validation Failed", "Approved", "Rejected"):
        print(json.dumps(rec.get("pipeline"), indent=1)[:6000], flush=True)
        break
    time.sleep(300)
