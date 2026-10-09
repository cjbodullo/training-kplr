#!/usr/bin/env bash
# Wait for a free slot in the 5 task validation queue, then submit drill-set
# once and hand over to the loop.  Never deletes anything: the tasks holding
# the queue belong to other sessions.
set -uo pipefail
cd /home/osboxes/Downloads/afterquery_kepler

state() {
    timeout 120 python3 kepler-tools/kepler_api.py list 2>/dev/null | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception:
    print("? ?"); sys.exit(0)
v=[t for t in d if t.get("status")=="Validating"]
mine=any(t.get("taskName")=="drill-set" for t in d)
print(len(v), "yes" if mine else "no")'
}

for tick in $(seq 1 240); do
    read -r n mine <<< "$(state)"
    echo "$(date -u +%H:%M:%S) validating=$n drill-set=$mine"
    if [ "$mine" = "yes" ]; then
        echo "drill-set is already in the queue, nothing to do"
        exit 0
    fi
    if [ "$n" != "?" ] && [ "$n" -lt 5 ] 2>/dev/null; then
        echo "=== slot free, submitting ==="
        python3 -u kepler-tools/kepler_run.py loop \
            --zip tasks/drill-set/drill-set.zip --name drill-set \
            --category Media --labels Design --src task-src/drill-set \
            --max-rounds 4 --interval 20
        rc=$?
        echo "loop exited $rc"
        read -r n2 mine2 <<< "$(state)"
        [ "$mine2" = "yes" ] && exit 0
        echo "submit did not land, back to waiting"
    fi
    sleep 120
done
echo "gave up waiting for a slot"
