import json, subprocess, sys, time
SID = "uhCx4lsZoXU8jBZ7NHBE"
last = None
deadline = time.time() + 8 * 3600
while time.time() < deadline:
    try:
        d = json.loads(subprocess.check_output(
            [sys.executable, "kepler-tools/kepler_api.py", "status", SID],
            text=True, timeout=180))
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
        dp = p.get("difficultyProbe") or {}
        if d.get("reviewStatus") in ("approved", "rejected") or p.get("failedStage") \
           or st("difficultyProbe") in ("passed", "failed"):
            print("FINAL", d.get("reviewStatus"), "band", dp.get("band"),
                  "passCount", dp.get("passCount"),
                  "| failed:", p.get("failedStage"), p.get("failureReason"), flush=True)
            break
    except Exception as exc:
        print(time.strftime("%H:%M:%S"), "poll error:", exc, flush=True)
    time.sleep(600)
