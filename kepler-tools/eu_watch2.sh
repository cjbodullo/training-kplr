#!/usr/bin/env bash
cd /home/osboxes/Downloads/afterquery_kepler
SID=uG9N8UQj7LZFYvFAgPr6
prev="$(timeout 100 python3 kepler-tools/eu_poll_id.py $SID 2>&1 | tr '\n' '|')"
for i in $(seq 1 40); do
    sleep 90
    now="$(timeout 100 python3 kepler-tools/eu_poll_id.py $SID 2>&1 | tr '\n' '|')"
    case "$now" in *"poll error"*) continue;; esac
    if [ "$now" != "$prev" ]; then echo "$now" | tr '|' '\n'; exit 0; fi
    case "$now" in *"TERMINAL: yes"*) echo "$now" | tr '|' '\n'; exit 0;; esac
done
echo "$now" | tr '|' '\n'
