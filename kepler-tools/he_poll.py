import json, subprocess, sys, time, os
SID = "PZEdQUu4zgqJflc72yiM"
ROOT = "/home/osboxes/Downloads/afterquery_kepler"
LOG = os.path.join(ROOT, "kepler-tools", "he_poll.log")
STAGES = ("structure","aiCheck","similarity","oracleNop","qualityCheck",
          "cheatProbe","easinessProbe","difficultyProbe","trajectoryReview")
last = None
for i in range(180):
    try:
        out = subprocess.run([sys.executable, os.path.join(ROOT,"kepler-tools","kepler_api.py"),
                              "status", SID], capture_output=True, text=True, timeout=180).stdout
        d = json.loads(out)
    except Exception as e:
        time.sleep(120); continue
    p = d.get("pipeline") or {}
    line = "%s status=%s stage=%s failed=%s | %s" % (
        time.strftime("%H:%M"), d.get("status"), p.get("stage"), p.get("failedStage"),
        " ".join("%s=%s" % (s, (p.get(s) or {}).get("status") if isinstance(p.get(s), dict) else None) for s in STAGES))
    if line[6:] != (last or "")[6:]:
        with open(LOG, "a") as fh:
            fh.write(line + "\n")
            for s in STAGES:
                v = p.get(s)
                if isinstance(v, dict) and v.get("status") not in (None, "passed", "running", "pending"):
                    fh.write("   %s -> %s\n" % (s, json.dumps(v)[:900]))
        last = line
    if d.get("status") != "Validating":
        with open(LOG, "a") as fh:
            fh.write("FINAL %s\n%s\n" % (d.get("status"), json.dumps(p)[:4000]))
        print("FINAL", d.get("status"))
        break
    time.sleep(180)
