#!/bin/bash
# abl.sh MODE... : run the reference solver in each mode against out/case and grade
cd "$(dirname "$0")"
A=/home/tobi/rs-work/abl
mkdir -p $A
for mode in "$@"; do
  echo "=== $mode"
  rm -rf $A/$mode
  docker run --rm -e RS_MODE=$mode -v ${CASE:-/home/tobi/rs-work/out/case}:/data/tarn:ro \
    -v /home/tobi/Desktop/Chris/anand_kepler/task-src/raid-salvage/solution:/solution:ro -v $A:/o rs-gen \
    sh -c "mkdir -p /tmp/tarn; for f in /data/tarn/*.xz; do xz -dc \$f > /tmp/tarn/\$(basename \$f .xz); done; cp /data/tarn/*.map /tmp/tarn/; for f in /data/tarn/*.img; do [ -e \$f ] && cp \$f /tmp/tarn/; done; python3 /solution/recover.py /tmp/tarn /o/$mode 2>/o/$mode.err; chown -R 1000:1000 /o" || { tail -5 $A/$mode.err; continue; }
  tail -2 $A/$mode.err
  python3 grade.py ${TRUTH:-/home/tobi/rs-work/out/sealed/truth.json} $A/$mode
done
