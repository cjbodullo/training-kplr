#!/usr/bin/env bash
# reference: roll the control backup back to the lot date with the operation history, settle the rest
# against the CMM reports, and cut the swept tool volumes out of the stock in CadQuery (OCCT)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/models
cd "$HERE"
python3 "$HERE/models.py" /app/cnc /app/shop /app/qc /app/models
ls -la /app/models
