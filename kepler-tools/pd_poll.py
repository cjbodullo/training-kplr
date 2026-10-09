#!/usr/bin/env python3
"""Emit one line per pipeline state change for a submission. Exits on terminal."""
import sys, time
sys.path.insert(0, 'kepler-tools')

SID = "eP1ezDmDc8NDg0fhL3yV"
STAGES = ("structure","aiCheck","similarity","oracleNop","qualityCheck",
          "cheatProbe","easinessProbe","difficultyProbe","trajectoryReview")

def snapshot():
    import kepler_api as api
    r = api.get(SID)
    p = r.get("pipeline") or {}
    bits = [f"status={r.get('status')}"]
    for k in STAGES:
        v = p.get(k)
        if isinstance(v, dict) and v.get("status"):
            s = f"{k}={v['status']}"
            if v.get("passCount") is not None:
                s += f"({v['passCount']}/{v.get('nAttempts')})"
            bits.append(s)
    if p.get("failedStage"):
        bits.append(f"FAILED_AT={p['failedStage']} reason={str(p.get('failureReason'))[:200]}")
    terminal = bool(p.get("failedStage")) or bool(p.get("completedAt")) or \
        str(r.get("status","")).lower() not in ("validating", "submitted", "pending")
    return " | ".join(bits), terminal

prev = None
for _ in range(400):
    try:
        line, terminal = snapshot()
    except Exception as exc:
        line, terminal = f"pollerror {type(exc).__name__}: {str(exc)[:120]}", False
        if prev and prev.startswith("pollerror"):
            line = None
    if line and line != prev:
        print(f"pinpoint-descent | {line}", flush=True)
        prev = line
    if terminal:
        break
    time.sleep(300)
