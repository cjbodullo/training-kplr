import json, subprocess, sys, time
SID = "SqvB5VfqeUx6FEaaqM7S"
last = None
deadline = time.time() + 6 * 3600
while time.time() < deadline:
    try:
        out = subprocess.check_output(
            [sys.executable, "kepler-tools/kepler_api.py", "status", SID],
            text=True, timeout=180)
        d = json.loads(out)
        p = d.get("pipeline") or {}
        def st(k):
            v = p.get(k)
            return v.get("status") if isinstance(v, dict) else v
        row = json.dumps({k: st(k) for k in (
            "structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
            "cheatProbe", "easinessProbe", "difficultyProbe", "trajectoryReview")}
            | {"stage": p.get("stage"), "failedStage": p.get("failedStage"),
               "failureReason": p.get("failureReason")}, sort_keys=True)
        if row != last:
            print(time.strftime("%H:%M:%S"), d.get("reviewStatus"), row, flush=True)
            last = row
        if d.get("reviewStatus") in ("approved", "rejected") or p.get("failedStage") \
           or st("difficultyProbe") in ("passed", "failed"):
            dp = p.get("difficultyProbe") or {}
            print("FINAL", d.get("reviewStatus"), "band", dp.get("band"),
                  "passCount", dp.get("passCount"), flush=True)
            break
    except Exception as exc:
        print(time.strftime("%H:%M:%S"), "poll error:", exc, flush=True)
    time.sleep(600)
