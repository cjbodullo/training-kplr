#!/bin/bash
# cheat_run.sh: build the sealed verifier image and grade every shortcut through the real
# test.sh. never shipped to the agent, never run by harbor. needs the rs-gen image and the
# ablation outputs from dev-gen/raid-salvage/abl.sh in $A.
#   writeoff  : every regular file in lost.txt, empty tar (no wrong bytes ever handed back)
#   giveall   : force assembled tar of all 112 files, empty lost.txt
#   force degraded bitmap offset dashonly : the five wrong readings of member currency
#   ref       : the reference, must be the only reward 1
set -u
here="$(cd "$(dirname "$0")" && pwd)"
A=${A:-/home/tobi/rs-work/abl}
docker build -q -t rs-verify "$here/../../task-src/raid-salvage/tests" >/dev/null
# writeoff: all paths from the reference outputs, none recovered
mkdir -p $A/writeoff $A/giveall
python3 - "$A" <<'PY'
import sys, tarfile, io
A = sys.argv[1]
names = []
with tarfile.open(f"{A}/ref/recovered.tar") as t:
    names = ["/" + m.name.lstrip("./") for m in t.getmembers() if m.isreg() or m.islnk()]
names += [l for l in open(f"{A}/ref/lost.txt").read().split("\n") if l]
open(f"{A}/writeoff/lost.txt", "w").write("\n".join(sorted(names)) + "\n")
tarfile.open(f"{A}/writeoff/recovered.tar", "w").close()
PY
cp $A/force/recovered.tar $A/giveall/; : > $A/giveall/lost.txt
for c in writeoff giveall force degraded bitmap offset dashonly noreplay norevoke uncommitted oldcopy wholeblock uninit noext noinode inplace norehab mtime ref; do
  rm -rf $A/logs-$c; mkdir -p $A/logs-$c
  docker run --rm -v $A/$c:/app/out:ro -v $A/logs-$c:/logs/verifier rs-verify bash /tests/test.sh >/dev/null 2>&1
  printf '%-9s reward %s  %s\n' $c "$(cat $A/logs-$c/reward.txt)" "$(grep -o '[0-9]* failed, [0-9]* passed\|[0-9]* passed' $A/logs-$c/pytest.txt | tail -1)"
done
