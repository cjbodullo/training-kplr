#!/usr/bin/env python3
"""Report consent-count's pipeline every five minutes until it is terminal."""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = ("structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "difficultyProbe", "easinessProbe", "runAudit",
          "trajectoryReview")
for _ in range(120):
    out = subprocess.run([sys.executable, os.path.join(HERE, "kepler_api.py"),
                          "list"], capture_output=True, text=True).stdout
    i = out.find("[")
    rows = json.loads(out[i:]) if i >= 0 else []
    me = [r for r in rows if r.get("taskName") == "consent-count"]
    if not me:
        print("%s  record gone" % time.strftime("%H:%M"), flush=True)
        break
    r = me[0]
    pl = r.get("pipeline") or {}
    bits = []
    for k in STAGES:
        v = pl.get(k)
        if isinstance(v, dict):
            bits.append("%s=%s" % (k, v.get("verdict") or v.get("status")
                                   or ("blocked" if v.get("blocked") else "ok")))
    print("%s  %s stage=%s  %s" % (time.strftime("%H:%M"), r.get("status"),
                                   pl.get("stage"), " ".join(bits)), flush=True)
    if r.get("status") not in ("Validating", "Submitted", "Queued"):
        print("TERMINAL: %s" % r.get("status"), flush=True)
        if r.get("rejection"):
            print(json.dumps(r["rejection"])[:1500], flush=True)
        break
    time.sleep(300)
