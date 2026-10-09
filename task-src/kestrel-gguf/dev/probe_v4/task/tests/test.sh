#!/usr/bin/env bash
# verifier entry point: always writes /logs/verifier/reward.txt (0 or 1) and ctrf.json
LOGDIR=/logs/verifier
mkdir -p "$LOGDIR"
echo 0 > "$LOGDIR/reward.txt"

cd /tests || exit 0
timeout 3000 python3 -m pytest /tests/test_port.py -p no:cacheprovider --ctrf "$LOGDIR/ctrf.json" -rA -v \
    > "$LOGDIR/pytest.txt" 2>&1
rc=$?
cat "$LOGDIR/pytest.txt"

if [ ! -s "$LOGDIR/ctrf.json" ]; then
    python3 - <<'PY' || true
import json
json.dump({"results": {"tool": {"name": "pytest"},
                       "summary": {"tests": 1, "passed": 0, "failed": 1, "pending": 0,
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
