#!/bin/bash
# usage: abeval.sh seeds files...
seeds=$1; shift
for f in "$@"; do
  echo "== $f"
  docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp -v $PWD:/dev2 -w /dev2 spike-sumo python3 evalfile.py $f $seeds 2>&1 | python3 -c "
import sys,re
bbmax=0; dd=0; fails=0; n=0
for l in sys.stdin:
    m=re.search(r'tele (\d+) arr (\d+)/(\d+) ddmax (\d+) bb (\d+) (\{.*\})', l)
    if not m: print(l.strip()); continue
    n+=1
    per=eval(m.group(6)); pm=max(per.values()) if per else 0
    print(f'  tele {m.group(1)} arr {m.group(2)}/{m.group(3)} dd {m.group(4)} bbmaxlink {pm}')
"
done
