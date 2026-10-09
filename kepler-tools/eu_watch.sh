#!/usr/bin/env bash
# Poll until the stage line changes or the submission goes terminal.
cd /home/osboxes/Downloads/afterquery_kepler
prev="$(timeout 90 python3 kepler-tools/poll_status.py exact-unlearn 2>&1 | tr '\n' '|')"
for i in $(seq 1 60); do
    sleep 90
    now="$(timeout 90 python3 kepler-tools/poll_status.py exact-unlearn 2>&1 | tr '\n' '|')"
    if [ "$now" != "$prev" ]; then
        echo "$now" | tr '|' '\n'
        exit 0
    fi
    if echo "$now" | grep -q "TERMINAL: yes"; then
        echo "$now" | tr '|' '\n'; exit 0
    fi
done
echo "$now" | tr '|' '\n'
