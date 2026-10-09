#!/bin/bash
# sweep_gen.sh FIRST LAST KILL_GAP : generate runs only, 5 containers at a time
cd "$(dirname "$0")"
for s in $(seq $1 $2); do
  docker run --rm -e KILL_GAP=$3 -e M4_BIAS=${M4_BIAS:-0} -e SWEEP_P=${SWEEP_P:-0.12} -v $PWD:/gen -w /gen etcdgen sh -c "python3 gen.py /gen/run_k$s $s >/dev/null 2>&1; chown -R $(id -u):$(id -g) /gen/run_k$s" &
  if (( (s - $1 + 1) % 5 == 0 )); then wait; fi
done
wait
