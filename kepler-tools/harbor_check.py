"""harbor check that works locally.

the reviewer container installs claude code from the CDN, which is too slow for the
installer's own deadline, and it has no login. this uploads the host's claude binary
(CLAUDE_HOST_BIN, default the vscode extension's) instead and raises the setup timeout.

usage, from task-src/<slug>/:
  CLAUDE_CODE_OAUTH_TOKEN="$(python3 -c "import json;print(json.load(open('$HOME/.claude/.credentials.json'))['claudeAiOauth']['accessToken'])")" \
    ~/.local/share/uv/tools/harbor/bin/python ../../kepler-tools/harbor_check.py . -m anthropic/claude-opus-4-8
the binary must be a linux x64 build the container can run.
"""
import glob
import os
import sys

from harbor.agents.base import BaseAgent
from harbor.agents.installed import base as ib

BaseAgent.DEFAULT_SETUP_TIMEOUT_SEC = 1800.0
_found = sorted(glob.glob(os.path.expanduser(
    "~/.vscode/extensions/anthropic.claude-code-*-linux-x64/resources/native-binary/claude")))
HOST_BIN = os.environ.get("CLAUDE_HOST_BIN") or (_found[-1] if _found else None)
if not HOST_BIN or not os.path.exists(HOST_BIN):
    raise SystemExit("no host claude binary: set CLAUDE_HOST_BIN")
_orig = ib.BaseInstalledAgent.exec_as_agent


async def exec_as_agent(self, environment, command, *a, **kw):
    if "bootstrap.sh" in command:
        await environment.upload_file(HOST_BIN, "/tmp/claude-bin")
        command = ("mkdir -p ~/.local/bin && cp /tmp/claude-bin ~/.local/bin/claude && "
                   "chmod +x ~/.local/bin/claude && "
                   "echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.bashrc && "
                   "export PATH=\"$HOME/.local/bin:$PATH\" && claude --version")
    return await _orig(self, environment, command, *a, **kw)


ib.BaseInstalledAgent.exec_as_agent = exec_as_agent
from harbor.cli.main import app  # noqa: E402
sys.argv = ["harbor", "check", *sys.argv[1:]]
sys.exit(app())
