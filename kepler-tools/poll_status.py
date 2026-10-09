#!/usr/bin/env python3
"""Print a compact one-shot status for the latest submission of a task name.
Ends with 'TERMINAL: yes|no|unknown' so the caller knows whether to keep polling."""
import sys
sys.path.insert(0, "/home/osboxes/Downloads/afterquery_kepler/kepler-tools")
import kepler_api as api

name = sys.argv[1] if len(sys.argv) > 1 else "mvcc-snapshot-isolation"
STAGES = [("structure", "structure"), ("aiCheck", "ai_check"), ("similarity", "similarity"),
          ("oracleNop", "oracle_nop"), ("qualityCheck", "quality"), ("cheatProbe", "cheat_probe"),
          ("difficultyProbe", "difficulty_probe"), ("trajectoryReview", "run_audit")]

def st(p, k):
    v = p.get(k)
    return v.get("status") if isinstance(v, dict) else ("pending" if v is None else v)

try:
    rows = api.list_mine()
    rows = rows if isinstance(rows, list) else rows.get("tasks", [])
    subs = [r for r in rows if r.get("taskName") == name]
    if not subs:
        print(f"no submission found for {name}")
        print("TERMINAL: unknown"); sys.exit(0)
    r = max(subs, key=lambda x: x.get("submittedAt") or x.get("createdAt") or 0)
    sid = r["id"]
    d = api.get(sid)
    p = d.get("pipeline") or {}
    print(f"submissionId: {sid}")
    print(f"status: {d.get('status')} | stage: {p.get('stage')} | failedStage: {p.get('failedStage')}")
    print("  ".join(f"{lbl}:{st(p, k)}" for k, lbl in STAGES))
    if p.get("failureReason"):
        print("reason:", p.get("failureReason"))
    passed = all(st(p, k) == "passed" for k, _ in STAGES)
    failed = p.get("stage") == "failed"
    approved = d.get("status") == "Approved"
    print("TERMINAL:", "yes" if (failed or approved or passed) else "no")
except api.TokenError as e:
    print("token issue:", e); print("TERMINAL: no")
except Exception as e:
    print("poll error:", e); print("TERMINAL: no")
