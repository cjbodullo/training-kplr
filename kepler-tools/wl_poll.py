import json, subprocess, sys, time
SID = "mj9omqjfbk1Xxm71Hks6"
prev = None
for _ in range(60):
    try:
        out = subprocess.run([sys.executable, "kepler-tools/kepler_api.py", "status", SID],
                             capture_output=True, text=True, timeout=120).stdout
        r = json.loads(out)
        p = r.get("pipeline", {})
        line = "%s status=%s stage=%s" % (time.strftime("%H:%M:%S"), r.get("status"), p.get("stage"))
        for k, v in p.items():
            if isinstance(v, dict) and v.get("verdict"):
                line += " | %s=%s" % (k, v.get("verdict"))
        if line[9:] != (prev or "")[9:]:
            print(line, flush=True)
            prev = line
        if r.get("status") not in ("Validating",):
            print("TERMINAL:", r.get("status"), json.dumps(p.get("rejection") or r.get("rejection") or {})[:400], flush=True)
            break
    except Exception as exc:
        print("poll error", exc, flush=True)
    time.sleep(300)
