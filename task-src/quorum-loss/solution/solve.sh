#!/usr/bin/env bash
# reference salvage: read both surviving wals with etcd-dump-logs, check every history the call logs allow,
# keep what all of them agree on, and snapshot it out of a scratch etcd.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/out
python3 "$here/recover.py" /data/tarn-kv /app/out
