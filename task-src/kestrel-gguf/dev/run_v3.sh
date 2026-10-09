#!/usr/bin/env bash
cd "$(dirname "$0")/.."
docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp -v $PWD:/t -w /t/dev kestrel-base \
  bash -c 'python repack.py /t/dev/kite_ckpt && python make_transcripts.py /t/dev/kite_ckpt' > dev/v3_sweep.log 2>&1
echo "V3_DONE rc=$?" >> dev/v3_sweep.log
