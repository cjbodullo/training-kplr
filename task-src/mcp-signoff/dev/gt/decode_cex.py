import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aig import Aig
g = Aig('model.aag', 'model.map')
ins = list(g.inputs); rl = g.inputs[g.inmap[('rst_n', 0)]]; ins.remove(rl)
lit2idx = {l: i for i, l in enumerate(g.inputs)}
idx2name = {v: k for k, v in g.inmap.items()}
# init input index -> latch names
initname = collections.defaultdict(list)
for line in open('model.map'):
    f = line.split()
    if f[0] == 'init' and '.' not in f[3] and not f[3].startswith('n'):
        initname[int(f[1])].append(f"{f[3]}[{f[2]}]")
vals = collections.defaultdict(dict)
for l in open(sys.argv[1]):
    m = re.match(r'pi(\d+)@(\d+)=(\d)', l.strip())
    if m:
        vals[int(m.group(2))][int(m.group(1))] = int(m.group(3))
T = max(vals) + 1
for t in range(T):
    v = vals[t]; bus = collections.defaultdict(int); inits = collections.defaultdict(int)
    for pi, b in v.items():
        oi = lit2idx[ins[pi]]
        if oi in idx2name:
            n, bit = idx2name[oi]; bus[n] |= b << bit
        elif t == 0 and oi in initname:
            for nm in initname[oi]:
                w, bit = nm[:-1].split('['); inits[w] |= b << int(bit)
    print(t, ' '.join(f"{k}={v:x}" for k, v in sorted(bus.items()) if k not in ('clk',)))
    if t == 0: print('  init:', ' '.join(f"{k}={v:x}" for k, v in sorted(inits.items())))
