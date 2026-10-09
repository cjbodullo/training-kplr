"""truth.json ({de|src: minage}) + netlist + pairs -> exceptions sdc."""
import json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aig import groups
net, pairs, truthf, out = sys.argv[1:5]
fl, grp, plist = groups(net, pairs)
truth = json.load(open(truthf))
by = collections.defaultdict(lambda: collections.defaultdict(list))
for src, end in plist:
    inst, pin = end.rsplit('/', 1)
    if pin != 'D' or not fl[inst]['DE']:
        continue
    n = truth[f"{fl[inst]['DE']}|{src}"] + 1
    if n > 1:
        by[n][src].append(end)
lines = ['# cicd multicycle exceptions, read after base.sdc']
for n in sorted(by):
    for src in sorted(by[n]):
        pins = ' '.join(sorted(by[n][src]))
        lines.append(f"set_multicycle_path {n} -setup -from [get_cells {src}] -to [get_pins {{{pins}}}]")
        lines.append(f"set_multicycle_path {n-1} -hold -from [get_cells {src}] -to [get_pins {{{pins}}}]")
open(out, 'w').write('\n'.join(lines) + '\n')
print(len(lines) - 1, 'lines', {n: sum(len(v) for v in by[n].values()) for n in by})
