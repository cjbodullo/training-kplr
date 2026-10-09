#!/bin/bash
# sweep.sh FIRST LAST : generate seeds in batches of 5 containers
cd "$(dirname "$0")"
for s in $(seq $1 $2); do
  docker run --rm -v $PWD:/gen -w /gen etcdgen sh -c "python3 gen.py /gen/run_h$s $s >/dev/null 2>&1; python3 truth.py /gen/run_h$s /gen/run_h$s/truth.json" > seed_h$s.out 2>&1 &
  if (( (s - $1 + 1) % 5 == 0 )); then wait; fi
done
wait
