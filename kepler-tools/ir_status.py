import json, subprocess, sys, os
ID = "TjMG2n1YrBQYzFkKvkoe"
ROOT = os.path.dirname(os.path.abspath(__file__))
raw = subprocess.run([sys.executable, os.path.join(ROOT, "kepler_api.py"), "status", ID],
                     capture_output=True, text=True).stdout
try:
    d = json.loads(raw)
except Exception:
    print("could not parse status:", raw[-600:]); sys.exit(0)
p = d.get("pipeline") or {}
print("status:", d.get("status"), "| stage:", p.get("stage"))
for k in ("structure", "aiCheck", "similarity", "oracleNop", "qualityCheck", "cheatProbe",
          "easinessProbe", "difficultyProbe", "trajectoryReview", "runAudit"):
    v = p.get(k)
    if isinstance(v, dict):
        extra = ""
        for f in ("oracle", "nop", "verdict", "hacked", "passCount", "nAttempts", "error"):
            if v.get(f) not in (None, [], ""):
                extra += " %s=%s" % (f, v[f])
        print("  %-17s %-9s%s" % (k, v.get("status"), extra))
term = d.get("status") in ("failed", "rejected", "needs_review", "approved", "passed")
print("TERMINAL" if term else "RUNNING")
