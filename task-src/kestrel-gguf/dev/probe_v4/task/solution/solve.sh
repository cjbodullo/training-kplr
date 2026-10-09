#!/usr/bin/env bash
set -euo pipefail
# exact port of the kestrel checkpoint onto llama.cpp's stock "llama" graph
python3 /solution/convert.py /app/kestrel /app/kestrel.gguf
# smoke run through the same harness the grading uses
printf 'The 3 ships left port at 0500, didn'"'"'t they?\n' > /tmp/smoke.txt
kestrel-logits /app/kestrel.gguf /tmp/smoke.txt /tmp/smoke.bin
ls -la /app/kestrel.gguf
