#!/usr/bin/env bash
# Wait for a validation slot, then submit rack-shift.  The queue caps at 5.
cd /home/osboxes/Downloads/afterquery_kepler || exit 1

sleep 5400
for attempt in $(seq 1 40); do
    n="$(python3 - <<'PY' 2>/dev/null
import json, subprocess
out = subprocess.run(["python3","kepler-tools/kepler_api.py","list"],
                     capture_output=True, text=True, timeout=180).stdout
d = json.loads(out[out.index("["):])
print(sum(1 for t in d if t.get("status") in ("Validating", "Submitted")))
PY
)"
    echo "$(date -u +%H:%M) queue=${n:-?}/5"
    if [ -n "$n" ] && [ "$n" -lt 5 ]; then
        echo "slot free, submitting"
        timeout 900 python3 kepler-tools/kepler_run.py submit \
            --zip tasks/gantry-load/gantry-load.zip --name gantry-load \
            --category Operations --labels "Logistics,Supply chain" 2>&1 | tail -4
        exit 0
    fi
    sleep 600
done
echo "gave up waiting for a slot"
exit 1
