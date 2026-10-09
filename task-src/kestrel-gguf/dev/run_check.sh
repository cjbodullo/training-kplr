#!/usr/bin/env bash
cd "$(dirname "$0")/zipcheck"
export CLAUDE_CODE_OAUTH_TOKEN="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude/.credentials.json')))['claudeAiOauth']['accessToken'])")"
timeout 3000 ~/.local/share/uv/tools/harbor/bin/python ../../../../kepler-tools/harbor_check.py . -m anthropic/claude-opus-4-8 > ../check.log 2>&1
echo "CHECK_RC=$?" >> ../check.log
