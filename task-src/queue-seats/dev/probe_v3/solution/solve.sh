#!/usr/bin/env bash
# reference: estimate ring, talk, after call work, patience and the transfer share from
# the asterisk queue_log, then size every half hour by steady state simulation.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
gcc -O2 -o "$WORK/qsim" "$HERE/qsim.c" -lm
# the march queue config the reference assumes
asterisk -V
grep -A3 '^\[faults\]' /app/pbx/queues.conf | grep -q 'wrapuptime = 60'
python3 "$HERE/plan.py" /app/pbx/queue_log /app/forecast/2027-03-01.csv "$WORK/qsim" /app/plan.csv
wc -l /app/plan.csv
