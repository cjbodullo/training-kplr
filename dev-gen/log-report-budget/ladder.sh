#!/bin/bash
O=/w/dev-gen/log-report-budget/out
NAIVE=/w/task-src/log-report-budget/environment/data/app/logstat/logstat
TUN='glibc.cpu.hwcaps=-AVX2_Usable,-AVX_Usable,-ERMS'
ir() {
  D=/w/dev-gen/log-report-budget/data/$2
  GLIBC_TUNABLES=$TUN valgrind --tool=callgrind --callgrind-out-file=/dev/null --trace-children=yes \
      "$1" $D/access.log $D/routes.tsv $D/deploys.csv $O/$2.$3.json 2>/tmp/cg.err
  N=$(sed -n 's/^==[0-9]*== I   refs: *//p' /tmp/cg.err | tr -d ', ' | python3 -c 'import sys;print(sum(int(x) for x in sys.stdin))')
  echo "$2 $3 $N"
}
for P in "$@"; do
  ir $O/fast $P ref
  ir $O/quick2 $P L2
  ir $O/quick $P L1
done
