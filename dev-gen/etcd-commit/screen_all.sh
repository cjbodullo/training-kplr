#!/bin/bash
# screen_all.sh RUN... : screen runs 6 at a time
cd "$(dirname "$0")"
n=0
for r in "$@"; do
  [ -f $r/screen.json ] && continue
  docker run --rm -v $PWD:/gen -w /gen etcdgen sh -c "python3 -W ignore screen.py /gen/$r > /gen/$r.screen.out 2>&1" &
  n=$((n+1)); if (( n % 6 == 0 )); then wait; fi
done
wait
