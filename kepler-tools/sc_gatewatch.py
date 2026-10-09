#!/usr/bin/env python3
"""watch for the similarity gate to recover, then say so.

a recovery is any submission on the account, from any session, whose
similarity stage passes AFTER this script starts. polls every 5 minutes.
"""
import json
import subprocess
import sys
import time

HERE = "/home/osboxes/Downloads/afterquery_kepler/kepler-tools"
START = int(time.time() * 1000)


def snapshot():
    out = subprocess.run([sys.executable, HERE + "/kepler_api.py", "list"],
                         capture_output=True, text=True, timeout=120)
    try:
        return json.loads(out.stdout)
    except Exception:
        return []


while True:
    rows = snapshot()
    fresh = [r for r in rows if (r.get("createdAt") or 0) >= START - 600000]
    for r in fresh:
        sim = ((r.get("pipeline") or {}).get("similarity") or {}).get("status")
        print("%s  %-14s %-11s sim=%s" % (time.strftime("%H:%M:%S"), r.get("taskName"),
                                          r.get("category"), sim), flush=True)
        if sim == "passed":
            print("GATE RECOVERED: %s passed similarity" % r.get("taskName"), flush=True)
            sys.exit(0)
    print("%s  no pass yet (%d fresh submissions seen)" % (time.strftime("%H:%M:%S"), len(fresh)),
          flush=True)
    time.sleep(300)
