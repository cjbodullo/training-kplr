#!/usr/bin/env python3
"""Compact pipeline status for one submission.  Exits 0 when terminal."""
import json
import subprocess
import sys

SID = sys.argv[1] if len(sys.argv) > 1 else "gKeEfI1nMqC0sY0jfTjX"

out = subprocess.run(["python3", "kepler-tools/kepler_api.py", "status", SID],
                     capture_output=True, text=True, timeout=180).stdout
i = out.index("{")
d = json.loads(out[i:])
if "result" in d:
    d = d["result"]["data"]["json"]

print("status :", d.get("status"), "| stage:", d.get("stage"))
pl = d.get("pipeline") or {}
order = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
         "cheatProbe", "easinessProbe", "difficultyProbe", "trajectoryReview",
         "runAudit"]
seen = []
for k in order + [k for k in pl if k not in order]:
    if k not in pl:
        continue
    v = pl[k]
    if not isinstance(v, dict):
        continue
    verdict = v.get("verdict") or v.get("status") or v.get("stage")
    extra = ""
    if v.get("solved") is not None:
        extra = f" solved={v.get('solved')}/{v.get('trials') or '?'}"
    if v.get("band"):
        extra += f" band={v.get('band')}"
    if v.get("failureKind"):
        extra += f" kind={v.get('failureKind')}"
    print(f"  {k:18s} {str(verdict):<10}{extra}")
    seen.append(verdict)

terminal = str(d.get("status")) in ("Needs Review", "Approved",
                                    "Validation Failed", "Rejected")
print("TERMINAL" if terminal else "running")
sys.exit(0 if terminal else 3)
