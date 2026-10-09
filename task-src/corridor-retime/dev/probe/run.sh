#!/bin/bash
cd "$(dirname "$0")/task"
export CLAUDE_CODE_OAUTH_TOKEN="$(python3 -c "import json;print(json.load(open('$HOME/.claude/.credentials.json'))['claudeAiOauth']['accessToken'])")"
exec ~/.local/share/uv/tools/harbor/bin/python /home/tobi/Desktop/Chris/anand_kepler/kepler-tools/harbor_probe.py -p . -a claude-code -m anthropic/claude-opus-5-5 --ak reasoning_effort=low -k 3 -n 2 -e docker
