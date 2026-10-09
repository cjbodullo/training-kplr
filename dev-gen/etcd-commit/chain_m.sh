#!/bin/bash
cd "$(dirname "$0")"
while pgrep -f "^/bin/bash ./sweep_gen.sh" >/dev/null; do sleep 15; done
./screen_all.sh $(ls -d run_k2[0-9][0-9]) > screen_m.log 2>&1
ls -d run_k2*/screen.json | sed 's#/screen.json##' > runs_m.txt
split -n l/4 runs_m.txt mpart_
for p in mpart_??; do docker run --rm -v $PWD:/gen -w /gen etcdgen python3 -W ignore tailscan.py $(cat $p) > $p.out 2>&1 & done; wait
cat mpart_??.out | sort -k5 -n -r > tail_m.txt
echo DONE >> tail_m.txt
