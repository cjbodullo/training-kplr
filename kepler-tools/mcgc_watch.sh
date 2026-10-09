#!/usr/bin/env bash
# Poll the mark-compact-gc submission until the pipeline stage changes, a stage
# fails, the run goes terminal, or a time cap is hit. Prints a compact line each
# poll and a final SNAPSHOT, then exits (which re-invokes the assistant).
set -uo pipefail
cd /home/Afterquery

SID=stYVriSCXSN7AFnFIoOY
CAP_ITERS=${1:-40}      # 40 * 30s = 20 min per watch chunk
prev_stage=""

for i in $(seq 1 "$CAP_ITERS"); do
  json=$(python3 kepler-tools/kepler_api.py status "$SID" 2>/dev/null)
  read -r overall stage failed kind <<<"$(printf '%s' "$json" | python3 -c "
import sys,json
d=json.load(sys.stdin); p=d.get('pipeline') or {}
print(d.get('status'), p.get('stage'), p.get('failedStage'), p.get('failureKind'))
" 2>/dev/null)"
  echo "[$(date +%H:%M:%S)] overall=$overall stage=$stage failed=$failed kind=$kind"
  if [ "$overall" != "Validating" ] || [ "$failed" != "None" ]; then
    echo "SNAPSHOT-TRIGGER: terminal-or-failed"
    python3 kepler-tools/mcgc_status.py
    exit 0
  fi
  if [ -n "$prev_stage" ] && [ "$stage" != "$prev_stage" ]; then
    echo "SNAPSHOT-TRIGGER: stage-advanced ($prev_stage -> $stage)"
    python3 kepler-tools/mcgc_status.py
    exit 0
  fi
  prev_stage="$stage"
  sleep 30
done
echo "SNAPSHOT-TRIGGER: time-cap"
python3 kepler-tools/mcgc_status.py
