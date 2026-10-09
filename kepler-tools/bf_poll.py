import json, subprocess, sys, time
SID = "gdcjMVWPkKAEAKdzGHFi"
seen = {}
while True:
    try:
        out = subprocess.run([sys.executable, "kepler-tools/kepler_api.py", "status", SID],
                             capture_output=True, text=True, timeout=120).stdout
        rec = json.loads(out)
    except Exception as exc:
        print("poll error: %s" % exc, flush=True); time.sleep(300); continue
    pipe = rec.get("pipeline") or {}
    status = rec.get("status")
    lines = []
    for name, st in pipe.items():
        if not isinstance(st, dict): continue
        v = st.get("verdict") or st.get("result") or st.get("status")
        if v is None: continue
        if seen.get(name) != v:
            seen[name] = v
            lines.append("%s = %s" % (name, v))
    if lines:
        print("[%s] %s | stage=%s" % (status, "; ".join(lines), pipe.get("stage")), flush=True)
    if status in ("Needs Review", "Validation Failed", "Approved", "Rejected"):
        print("TERMINAL: %s | stage=%s" % (status, pipe.get("stage")), flush=True)
        err = None
        for name, st in pipe.items():
            if isinstance(st, dict) and (st.get("verdict") or st.get("result")) in ("fail","failed"):
                err = (name, json.dumps(st)[:1500])
        if err: print("FAILED STAGE %s: %s" % err, flush=True)
        break
    time.sleep(300)
