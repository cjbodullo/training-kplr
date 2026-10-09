import json, subprocess, sys, time
SID = "sGHUc7fX8pHLtwgUxEgz"
last = None
deadline = time.time() + 6 * 3600
while time.time() < deadline:
    try:
        out = subprocess.check_output(
            [sys.executable, "kepler-tools/kepler_api.py", "status", SID],
            text=True, timeout=180)
        d = json.loads(out)
        p = d.get("pipeline") or {}
        row = json.dumps({k: p.get(k) for k in (
            "stage", "structure", "aiCheck", "similarity", "oracleNop",
            "qualityCheck", "cheatProbe", "easinessProbe", "difficultyProbe",
            "trajectoryReview", "failedStage", "failureReason", "failureKind")},
            sort_keys=True)
        if row != last:
            print(time.strftime("%H:%M:%S"), d.get("reviewStatus"), row, flush=True)
            last = row
        if d.get("reviewStatus") in ("approved", "rejected") or p.get("failedStage"):
            print("VERDICT", d.get("reviewStatus"), json.dumps(d.get("rejection")), flush=True)
            break
    except Exception as exc:
        print(time.strftime("%H:%M:%S"), "poll error:", exc, flush=True)
    time.sleep(600)
