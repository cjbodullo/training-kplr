#!/usr/bin/env python3
"""Poll inbox-catchup every 5 minutes; log every stage transition."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kepler_api as k

SID = "wohHWHYPB7yIdEVrLjDg"
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ic_poll.log")
KEYS = ("structure","aiCheck","similarity","oracleNop","qualityCheck",
        "cheatProbe","easinessProbe","difficultyProbe","runAudit")

def snap():
    r = k.get(SID)
    p = r.get("pipeline") or {}
    out = {"status": r.get("status"), "stage": p.get("stage"),
           "failedStage": p.get("failedStage"),
           "failureReason": (p.get("failureReason") or "")[:400]}
    for key in KEYS:
        v = p.get(key)
        if isinstance(v, dict):
            out[key] = {kk: v.get(kk) for kk in
                        ("status","passed","blocked","verdict","band",
                         "passCount","maxPasses","error") if kk in v}
    return out

last = None
while True:
    try:
        cur = snap()
    except Exception as exc:
        cur = {"status": "poll-error", "err": repr(exc)[:200]}
    if cur != last:
        with open(LOG, "a") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), json.dumps(cur)))
        last = cur
    if cur.get("status") in ("Needs Review", "Validation Failed", "Approved", "Rejected"):
        break
    time.sleep(300)
