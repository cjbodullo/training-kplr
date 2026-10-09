import json, subprocess, sys, time
SID = "GHG8LO3SX8IrAHHe3dn8"
ROOT = "/home/osboxes/Downloads/afterquery_kepler"
TERMINAL = ("passed", "failed", "rejected", "needs_review", "needsReview", "approved")
last = None
while True:
    try:
        out = subprocess.run([sys.executable, f"{ROOT}/kepler-tools/kepler_api.py", "status", SID],
                             capture_output=True, text=True, timeout=120).stdout
        i = out.find("{")
        d = json.loads(out[i:]) if i >= 0 else {}
    except Exception as e:
        print("poll error:", e, flush=True); time.sleep(300); continue
    v = d.get("validation", d) or {}
    st = d.get("status") or v.get("status")
    parts = []
    for k in ("structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
              "cheatProbe", "easinessProbe", "difficultyProbe", "runAudit"):
        s = v.get(k)
        if isinstance(s, dict) and s.get("status"):
            parts.append(f"{k}={s['status']}")
    sig = f"{st} | " + " ".join(parts)
    if sig != last:
        print(time.strftime("%H:%M"), sig, flush=True)
        last = sig
    if st and str(st).lower() in TERMINAL:
        print("TERMINAL:", st, flush=True)
        print(json.dumps(v, indent=1)[:3000], flush=True)
        break
    time.sleep(300)
