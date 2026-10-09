#!/bin/bash
# wait until the oauth token rotates (fresh ~8 h token), then run the probe with it
C=$HOME/.claude/.credentials.json
P="$(cd "$(dirname "$0")" && pwd)"
exp() { python3 -c "import json;print(json.load(open('$C'))['claudeAiOauth']['expiresAt'])"; }
left() { python3 -c "import json,time;print(int(json.load(open('$C'))['claudeAiOauth']['expiresAt']/1000-time.time()))"; }
old=$(exp)
# a token with more than 5 h left is good enough to start now
while [ "$(exp)" = "$old" ] && [ "$(left)" -lt 18000 ]; do sleep 30; done
sleep 20
echo "launching with token valid for $(( $(left) / 60 )) min at $(date)"
mkdir -p "$P/old"; [ -d "$P/task/jobs" ] && mv "$P/task/jobs" "$P/old/jobs_$(date +%H%M%S)"
docker ps -a --format '{{.Names}}' | grep -i "^task__" | xargs -r docker rm -f >/dev/null
exec "$P/run.sh"
