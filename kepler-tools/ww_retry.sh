#!/usr/bin/env bash
# retry the whole loop when it dies on an API/rate-limit error (exit 4).
cd /home/osboxes/Downloads/afterquery_kepler
for i in 1 2 3 4 5 6; do
  echo "### wrapper attempt $i at $(date +%H:%M:%S)"
  python3 -u kepler-tools/kepler_run.py loop \
    --zip $PWD/tasks/warn-wording/warn-wording.zip --name warn-wording \
    --category ML --labels Inference \
    --src $PWD/task-src/warn-wording \
    --max-rounds 4 --interval 20 \
    --similarity-gap 5400 --similarity-retries 3 \
    --start-delay $((60 + RANDOM % 120))
  rc=$?
  echo "### loop exited $rc at $(date +%H:%M:%S)"
  [ "$rc" -ne 4 ] && break
  sleep $((180 + RANDOM % 180))
done
