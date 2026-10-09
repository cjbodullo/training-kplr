#!/usr/bin/env bash
# detached poller for media-reclaim: appends a stamped status line every 5 min
cd /home/osboxes/Downloads/afterquery_kepler
LOG=/home/osboxes/Downloads/afterquery_kepler/task-src/media-reclaim/dev/pipeline.log
while true; do
  out=$(timeout 120 python3 kepler-tools/poll_status.py media-reclaim 2>&1 | sed -n '2,3p' | tr '\n' ' ')
  printf '%s %s\n' "$(date -u +%H:%M:%S)" "$out" >> "$LOG"
  case "$out" in
    *"Needs Review"*|*Approved*|*Rejected*|*"failedStage: "[a-z]*) exit 0;;
  esac
  sleep 300
done
