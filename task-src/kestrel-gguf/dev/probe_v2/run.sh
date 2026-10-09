#!/usr/bin/env bash
cd "$(dirname "$0")/task"
export CLAUDE_CODE_OAUTH_TOKEN="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude/.credentials.json')))['claudeAiOauth']['accessToken'])")"
~/.local/share/uv/tools/harbor/bin/python ../../../../../kepler-tools/harbor_probe.py -p . -o ../jobs -a claude-code \
  -m anthropic/claude-opus-5-5 --ak reasoning_effort=low -k 3 -n 3 -e docker > ../probe.log 2>&1
echo "PROBE_RC=$?" >> ../probe.log
