#!/usr/bin/env bash
cd /home/osboxes/Downloads/afterquery_kepler
last=""
for i in $(seq 1 80); do
  sleep 300
  now=$(python3 kepler-tools/poll_status.py warn-wording 2>&1 | tail -12)
  if [ "$now" != "$last" ]; then
    echo "--- $(date +%H:%M:%S) ---"; echo "$now"; tail -3 kepler-tools/ww_loop.log
    last="$now"
  fi
  echo "$now" | grep -q "TERMINAL: yes" && { echo "TERMINAL"; break; }
  pgrep -f "kepler_run.py loop" | grep -q . || { echo "NO LOOPS LEFT"; break; }
done
