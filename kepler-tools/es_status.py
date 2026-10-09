import json, os, subprocess, sys
ID = "dcqLz9A7EbP83jCbwVlQ"
ROOT = os.path.dirname(os.path.abspath(__file__))
raw = subprocess.run([sys.executable, os.path.join(ROOT, "kepler_api.py"), "status", ID],
                     capture_output=True, text=True).stdout
try:
    d = json.loads(raw)
except Exception:
    print("could not parse:", raw[-400:]); sys.exit(0)
p = d.get("pipeline") or {}
out = ["status=%s stage=%s" % (d.get("status"), p.get("stage"))]
for k in ("structure","aiCheck","similarity","oracleNop","qualityCheck","cheatProbe",
          "easinessProbe","difficultyProbe","trajectoryReview","runAudit"):
    v = p.get(k)
    if isinstance(v, dict):
        extra = "".join(" %s=%s" % (f, v[f]) for f in
                        ("oracle","nop","verdict","hacked","passCount","nAttempts","error")
                        if v.get(f) not in (None, [], ""))
        out.append("  %-17s %-9s%s" % (k, v.get("status"), extra))
if p.get("failureReason"): out.append("  REASON: %s" % p["failureReason"])
print("\n".join(out))
