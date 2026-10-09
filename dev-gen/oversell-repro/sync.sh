#!/usr/bin/env bash
# rebuild the verifier's copies from the shipped service tree
set -euo pipefail
ROOT=/root/work/anand_kepler/task-src/oversell-repro
DEV=/root/work/anand_kepler/dev-gen/oversell-repro

rm -rf "$ROOT/tests/service_current" "$ROOT/tests/service_fixed" "$ROOT/tests/data" "$ROOT/tests/stack"
mkdir -p "$ROOT/tests/stack"
cp -r "$ROOT/environment/service" "$ROOT/tests/service_current"
find "$ROOT/tests/service_current" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
python3 "$DEV/make_fixed.py" "$ROOT/tests/service_current" "$ROOT/tests/service_fixed"
cp -r "$ROOT/environment/data" "$ROOT/tests/data"
mkdir -p "$ROOT/tests/stack/scripts"
cp -r "$ROOT/environment/ops" "$ROOT/tests/stack/ops"
cp "$ROOT/environment/scripts/stack.sh" "$ROOT/tests/stack/scripts/stack.sh"
chmod +x "$ROOT/tests/stack/scripts/stack.sh"
echo "synced"
