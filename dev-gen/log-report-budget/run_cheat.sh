#!/bin/bash
# Runs one cheat attempt through the real verifier image.
#
#   run_cheat.sh <cheat-script-name>       e.g. run_cheat.sh symlink_output.sh
#
# Builds the agent image, applies the cheat inside it, copies /app/logstat/src
# out, drops it into a fresh verifier container and runs /tests/test.sh, the
# same way harbor does.
set -eu
BUNDLE=/root/work/anand_kepler/task-src/log-report-budget
CHEAT=$1
WORK=$(mktemp -d /tmp/cheat.XXXXXX)

docker build -q -t lrb-env "$BUNDLE/environment" >/dev/null
docker build -q -t lrb-tests "$BUNDLE/tests" >/dev/null

cid=$(docker create lrb-env sleep 600)
docker start "$cid" >/dev/null
docker cp "$BUNDLE/solution/." "$cid:/solution" >/dev/null
docker cp "$BUNDLE/cheat/." "$cid:/cheat" >/dev/null
set +e
docker exec "$cid" sh -c "sh /cheat/$CHEAT" > "$WORK/cheat.log" 2>&1
rc=$?
set -e
echo "cheat script exit: $rc"
tail -3 "$WORK/cheat.log"
docker cp "$cid:/app/logstat/src/." "$WORK/src" >/dev/null || mkdir -p "$WORK/src"
docker rm -f "$cid" >/dev/null

vid=$(docker create lrb-tests sleep 3600)
docker start "$vid" >/dev/null
docker exec "$vid" mkdir -p /app/logstat/src
docker cp "$WORK/src/." "$vid:/app/logstat/src" >/dev/null
docker exec "$vid" sh /tests/test.sh > "$WORK/test.log" 2>&1 || true
echo "reward: $(docker exec "$vid" cat /logs/verifier/reward.txt)"
docker exec "$vid" sh -c 'grep -E "PASSED|FAILED|ERROR" /logs/verifier/pytest.txt | head -25' || true
docker exec "$vid" sh -c 'cat /logs/verifier/grade.json' 2>/dev/null | head -40 || true
docker rm -f "$vid" >/dev/null
echo "logs in $WORK"
