import json, subprocess, sys, time
SID = "H8RnRryUnLP5lrfmvccJ"
ROOT = "/home/osboxes/Downloads/afterquery_kepler"
STAGES = ('structure','aiCheck','similarity','oracleNop','qualityCheck',
          'cheatProbe','easinessProbe','difficultyProbe','trajectoryReview')
last = None
while True:
    try:
        out = subprocess.run([sys.executable, f"{ROOT}/kepler-tools/kepler_api.py", "status", SID],
                             capture_output=True, text=True, timeout=150).stdout
        i = out.find("{"); d = json.loads(out[i:])
    except Exception as e:
        print("poll error:", e, flush=True); time.sleep(300); continue
    p = d.get("pipeline", {}) or {}
    st = str(d.get("status") or "")
    parts = [f"{k}={p[k].get('status')}" for k in STAGES
             if isinstance(p.get(k), dict) and p[k].get("status")]
    fs = p.get("failedStage"); fr = (p.get("failureReason") or "")[:300]
    sig = st + " | " + " ".join(parts) + (f" | FAILED@{fs}: {fr}" if fs else "")
    if sig != last:
        print(time.strftime("%H:%M"), sig, flush=True); last = sig
    if fs or st.lower() not in ("validating", "pending", "queued", "running", ""):
        print("TERMINAL:", st, "failedStage:", fs, flush=True)
        print(json.dumps(p, indent=1)[:4000], flush=True)
        break
    time.sleep(300)
