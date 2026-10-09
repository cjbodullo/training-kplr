#!/usr/bin/env python3
"""One-shot compact pipeline status for a submissionId."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kepler_api as api

sid = sys.argv[1]
STAGES = [("structure", "structure"), ("aiCheck", "ai_check"), ("similarity", "similarity"),
          ("oracleNop", "oracle_nop"), ("qualityCheck", "quality"), ("cheatProbe", "cheat_probe"),
          ("easinessProbe", "easiness"), ("difficultyProbe", "difficulty"),
          ("trajectoryReview", "run_audit")]

def st(p, k):
    v = p.get(k)
    return v.get("status") if isinstance(v, dict) else ("pending" if v is None else v)

d = api.get(sid)
p = d.get("pipeline") or {}
status = d.get("status")
print("status=%s stage=%s failed=%s | %s" % (
    status, p.get("stage"), p.get("failedStage"),
    " ".join("%s:%s" % (lbl, st(p, k)) for k, lbl in STAGES)))
terminal = status in ("passed", "failed", "rejected", "approved", "needs_review",
                      "needsReview", "awaiting_review") or bool(p.get("failedStage"))
print("TERMINAL: %s" % ("yes" if terminal else "no"))
