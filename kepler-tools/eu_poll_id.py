#!/usr/bin/env python3
"""Compact status for one submission id. Avoids listMine, which has been timing out."""
import sys
sys.path.insert(0, "/home/osboxes/Downloads/afterquery_kepler/kepler-tools")
import kepler_api as api

STAGES = [("structure", "structure"), ("aiCheck", "ai_check"), ("similarity", "similarity"),
          ("oracleNop", "oracle_nop"), ("qualityCheck", "quality"), ("cheatProbe", "cheat_probe"),
          ("difficultyProbe", "difficulty_probe"), ("trajectoryReview", "run_audit")]

def st(p, k):
    v = p.get(k)
    return v.get("status") if isinstance(v, dict) else ("pending" if v is None else v)

sid = sys.argv[1]
d = api.get(sid)
p = d.get("pipeline") or {}
print(f"status: {d.get('status')} | stage: {p.get('stage')} | failedStage: {p.get('failedStage')}")
print("  ".join(f"{lbl}:{st(p, k)}" for k, lbl in STAGES))
fs = p.get("failedStage")
if fs:
    node = p.get(fs) if isinstance(p.get(fs), dict) else {}
    print("reason:", (p.get("failureReason") or node.get("reason") or "")[:400])
term = d.get("status") in ("Needs Review", "Approved", "Rejected") or bool(fs)
print("TERMINAL:", "yes" if term else "no")
