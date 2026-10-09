#!/usr/bin/env python3
"""Compact, resilient status view for the mark-compact-gc submission.

Retries on the Vercel 403 checkpoint / transient non-JSON with backoff so a
single hiccup does not blank the report.
"""
import json, subprocess, sys, os, time

SID = "q0rKEa2ZX4sCZV99MMjv"
HERE = os.path.dirname(os.path.abspath(__file__))


def fetch():
    return subprocess.run(
        [sys.executable, os.path.join(HERE, "kepler_api.py"), "status", SID],
        capture_output=True, text=True,
    ).stdout


def load():
    for attempt in range(4):
        out = fetch()
        try:
            return json.loads(out)
        except Exception:
            if attempt < 3:
                time.sleep(15 * (attempt + 1))
    return None


d = load()
if d is None:
    print("STATUS: unavailable (API blocked/non-JSON after retries) — will retry next tick")
    sys.exit(0)

p = d.get("pipeline") or {}


def st(x):
    return x.get("status") if isinstance(x, dict) else x


print("overall:", d.get("status"), "| stage:", p.get("stage"),
      "| failedStage:", p.get("failedStage"), "| failureKind:", p.get("failureKind"))
for k in ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "difficultyProbe", "trajectoryReview"]:
    v = p.get(k)
    extra = ""
    if isinstance(v, dict):
        if k == "oracleNop":
            extra = f" oracle={v.get('oracle')} nop={v.get('nop')} n={v.get('nAttempts')}"
        if k == "difficultyProbe":
            extra = f" solved={v.get('nSolved')}/{v.get('nAttempts')}"
        if v.get("error"):
            extra += f" ERR={str(v.get('error'))[:80]}"
    print(f"  {k:16} {str(st(v)):10}{extra}")
if p.get("failureReason"):
    print("REASON:", str(p.get("failureReason"))[:800])
