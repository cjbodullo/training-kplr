#!/usr/bin/env bash
# emit one line per pipeline stage change, exit when terminal
cd /home/osboxes/Downloads/afterquery_kepler
ID=FrWefngP6Xun2uiuEyjK
prev=""
while true; do
  cur=$(timeout 90 python3 - "$ID" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "kepler-tools")
import kepler_api as K
try:
    r = K.get(sys.argv[1])
except Exception as exc:
    print("poll-error %s" % exc); raise SystemExit
p = r.get("pipeline") or {}
st = r.get("status", "?")
parts = []
for name, v in p.items():
    if not isinstance(v, dict):
        continue
    stage = v.get("stage") or v.get("status") or ""
    res = v.get("result") or {}
    verdict = res.get("verdict") or res.get("band") or ""
    pc = res.get("passCount")
    bit = name + ":" + str(stage)
    if verdict:
        bit += "/" + str(verdict)
    if pc is not None:
        bit += "(pass %s)" % pc
    parts.append(bit)
print("status=%s | %s" % (st, " ".join(sorted(parts))))
PY
)
  [ -z "$cur" ] && cur="poll returned nothing"
  if [ "$cur" != "$prev" ]; then
    echo "$cur"
    prev="$cur"
  fi
  case "$cur" in
    *"status=Needs Review"*|*"status=Approved"*|*"status=Validation Failed"*|*"status=Rejected"*)
      echo "TERMINAL: $cur"; exit 0;;
  esac
  sleep 300
done
