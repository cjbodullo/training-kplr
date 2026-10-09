#!/usr/bin/env python3
"""Poll one submission; exit when a stage finishes or the run is terminal."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kepler_api as K

SID = sys.argv[1]
BASE = int(sys.argv[2]) if len(sys.argv) > 2 else -1
LOG = "/home/osboxes/Downloads/afterquery_kepler/kepler-tools/rt_poll.log"

def snap():
    r = K.get(SID)
    st = r.get("status")
    pipe = r.get("pipeline") or {}
    stages = pipe.get("stages") or pipe
    done = []
    if isinstance(stages, list):
        for s in stages:
            done.append((s.get("name"), s.get("status"), s.get("verdict")))
    elif isinstance(stages, dict):
        for k, v in stages.items():
            if isinstance(v, dict):
                done.append((k, v.get("status"), v.get("verdict")))
    return st, done, r

deadline = time.time() + 5400
while time.time() < deadline:
    try:
        st, done, raw = snap()
    except Exception as e:
        time.sleep(60); continue
    fin = [d for d in done if d[1] not in (None, "running", "pending", "queued")]
    line = "%s status=%s finished=%d %s" % (
        time.strftime("%H:%M:%S"), st, len(fin),
        " ".join("%s:%s" % (n, v or s) for n, s, v in done))
    open(LOG, "a").write(line + "\n")
    if st not in ("Validating", None) or (BASE >= 0 and len(fin) > BASE):
        print(line)
        json.dump(raw, open(LOG.replace(".log", ".json"), "w"), indent=1)
        sys.exit(0)
    time.sleep(60)
print("timeout")
