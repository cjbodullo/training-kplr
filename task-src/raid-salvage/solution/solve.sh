#!/usr/bin/env bash
# reference salvage: unpack the member images, rebuild the array in userspace from the
# superblocks, bitmap and mapfiles, then let debugfs read the filesystem back out.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work=/tmp/tarn
mkdir -p "$work" /app/out
for f in /data/tarn/bay*.img.xz; do
    xz -dc "$f" > "$work/$(basename "$f" .xz)"
done
cp /data/tarn/bay*.map "$work/"
python3 "$here/recover.py" "$work" /app/out
