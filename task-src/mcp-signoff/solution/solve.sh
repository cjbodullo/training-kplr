#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$here/solve.py"
test -s /app/exceptions.sdc
echo "wrote /app/exceptions.sdc ($(grep -c '^set_multicycle_path' /app/exceptions.sdc) commands)"
