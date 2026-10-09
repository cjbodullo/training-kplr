#!/usr/bin/env bash
# wait for a live bearer token from the bridge, delete the easiness-failed v1,
# then submit protocol-clone v2 and drive the pipeline loop.
set -uo pipefail
cd /home/osboxes/Downloads/afterquery_kepler2

OLD=XosTVznpHJDeVGtvUCjS
DEADLINE=$(( $(date +%s) + 7200 ))

while :; do
    left=$(timeout 30 python3 kepler-tools/kepler_api.py whoami 2>/dev/null \
           | python3 -c "import sys,json; print(json.load(sys.stdin).get('minutes_left', -999))" 2>/dev/null)
    case "$left" in
        ''|*[!0-9-]*) left=-999 ;;
    esac
    if [ "$left" -gt 2 ] 2>/dev/null; then
        echo "$(date -Is) token live, ${left} minutes left."
        break
    fi
    if [ "$(date +%s)" -ge "$DEADLINE" ]; then
        echo "$(date -Is) gave up waiting for a live token (last minutes_left=${left})"
        exit 2
    fi
    sleep 30
done

echo "$(date -Is) deleting structure-failed submission ${OLD}"
timeout 60 python3 kepler-tools/kepler_api.py delete "$OLD" || echo "delete failed (may already be gone)"

exec python3 -u kepler-tools/kepler_run.py loop \
    --zip tasks/protocol-clone/protocol-clone.zip \
    --name protocol-clone \
    --category Software \
    --labels Systems \
    --src task-src/protocol-clone \
    --interval 15
