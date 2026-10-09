#!/usr/bin/env bash
# Watch teaching-set's easiness/difficulty verdict.
cd /home/osboxes/Downloads/afterquery_kepler
SID=oN9Wyb9sdvCcfFdx6R07
for i in $(seq 1 200); do
    now="$(timeout 100 python3 kepler-tools/eu_poll_id.py $SID 2>&1)"
    case "$now" in *"poll error"*) sleep 60; continue;; esac
    if echo "$now" | grep -qE "easiness|difficulty" && echo "$now" | grep -qE "easi.*(passed|failed)|TERMINAL: yes"; then
        echo "$now"; exit 0
    fi
    if echo "$now" | grep -q "TERMINAL: yes"; then echo "$now"; exit 0; fi
    sleep 90
done
echo "$now"
