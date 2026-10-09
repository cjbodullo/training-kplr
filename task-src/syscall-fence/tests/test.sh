#!/usr/bin/env bash
# verifier entry point. always writes /logs/verifier/reward.txt (0 or 1) and a
# CTRF report, on every path including crashes.
set -u

LOGDIR=/logs/verifier
mkdir -p "$LOGDIR"
echo 0 > "$LOGDIR/reward.txt"   # default to fail until pytest says otherwise

python3 -m pytest /tests/test_fence.py -p no:cacheprovider \
    --ctrf "$LOGDIR/ctrf.json" -rA -vv > "$LOGDIR/pytest.txt" 2>&1
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

echo "reward=$(cat "$LOGDIR/reward.txt")"
exit 0
