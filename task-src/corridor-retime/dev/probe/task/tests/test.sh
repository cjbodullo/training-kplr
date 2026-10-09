#!/usr/bin/env bash
# verifier entry point: check /app/am_peak.add.xml and run it in sumo over the sealed days, always write a reward
LOGDIR=/logs/verifier
mkdir -p "$LOGDIR"
echo 0 > "$LOGDIR/reward.txt"

cd /tests
python3 -m pytest /tests/test_plan.py -p no:cacheprovider --ctrf "$LOGDIR/ctrf.json" -rA -vv -s \
    > "$LOGDIR/pytest.txt" 2>&1
rc=$?
cat "$LOGDIR/pytest.txt"

if [ ! -s "$LOGDIR/ctrf.json" ]; then
    python3 - <<'PY' || true
import json
json.dump({"results": {"tool": {"name": "pytest"},
                       "summary": {"tests": 0, "passed": 0, "failed": 1, "pending": 0,
                                   "skipped": 0, "other": 0, "start": 0, "stop": 0},
                       "tests": [{"name": "collection", "status": "failed", "duration": 0}]}},
          open("/logs/verifier/ctrf.json", "w"))
PY
fi

if [ "$rc" -eq 0 ]; then
    echo 1 > "$LOGDIR/reward.txt"
else
    echo 0 > "$LOGDIR/reward.txt"
fi
exit 0
