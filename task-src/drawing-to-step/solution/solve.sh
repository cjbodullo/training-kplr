#!/bin/bash
# reference: model the three prints in CadQuery from their dimension text (see models.py)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/models
python3 "$HERE/models.py" /app/models
ls -la /app/models
