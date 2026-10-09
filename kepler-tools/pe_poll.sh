#!/usr/bin/env bash
cd /home/osboxes/Downloads/afterquery_kepler
for i in $(seq 1 200); do
  python3 - <<'PY' >> task-src/pane-emit/status.log 2>&1
import sys, time; sys.path.insert(0,'kepler-tools')
import kepler_api as K
try:
    r = K.get('ADxL19tAxDDrme8U36uf')
except Exception as e:
    print(time.strftime('%H:%M:%S'), 'poll error', e); raise SystemExit
p = r.get('pipeline') or {}
st = [f"{k}:{v.get('status')}" for k, v in p.items() if isinstance(v, dict)]
print(time.strftime('%H:%M:%S'), r.get('status'), '|', ' '.join(st))
for k, v in p.items():
    if isinstance(v, dict) and v.get('status') in ('failed',):
        print('   FAILED', k, 'kind=', v.get('failureKind'), 'err=', str(v.get('error'))[:300])
PY
  s=$(tail -1 task-src/pane-emit/status.log)
  case "$s" in
    *"Needs Review"*|*Approved*|*"Validation Failed"*) echo "TERMINAL: $s" >> task-src/pane-emit/status.log; break;;
  esac
  sleep 300
done
