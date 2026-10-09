"""prove lower bounds on source stability at capture with abc pdr.

for every (enable net g, source flop S) pair and a candidate k, the property
is: whenever g is high, S has held its value for the previous k cycles
(windows reaching before cycle 0 are truncated when conv=0, and count as a
change when conv=1). rst_n is low on cycle 0 and high afterwards.

usage: prove.py model.aag model.map netlist.v pairs_base.txt cand.json conv out.json
cand.json: {"g|S": k, ...}
"""
import json
import os
import subprocess
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aig import Aig, groups


def build(g, fl, props, conv, path):
    """props: list of (de_net, src, k). writes an aag with one output per prop."""
    M = g.M
    inputs = list(g.inputs)
    latches = list(g.latches)
    ands = list(g.ands)
    # rst_n becomes a latch: 0 on cycle 0, then 1
    rl = g.inputs[g.inmap[('rst_n', 0)]]
    inputs.remove(rl)
    latches.append((rl, 1, 0))
    if os.environ.get('INIT0'):
        # power-up values of unreset flops pinned to 0
        for ii in sorted(g.initinputs):
            l = g.inputs[ii]
            inputs.remove(l)
            latches.append((l, 0, 0))
    nv = [M]

    def new():
        nv[0] += 1
        return nv[0] * 2

    def AND(a, b):
        l = new()
        ands.append((l, a, b))
        return l

    def OR(a, b):
        return AND(a ^ 1, b ^ 1) ^ 1

    def XOR(a, b):
        return OR(AND(a, b ^ 1), AND(a ^ 1, b))

    kmax = max(k for _, _, k in props)
    # valid chain v[j] = cycle >= j
    v = [1]
    for j in range(1, kmax + 1):
        l = new()
        latches.append((l, v[-1], 0))
        v.append(l)
    hist = {}
    for d, s, k in props:
        q = g.out_lit(fl[s]['Q'])
        h = hist.setdefault(s, [q])
        while len(h) < k + 1:
            l = new()
            latches.append((l, h[-1], 0))
            h.append(l)
    outs = []
    for d, s, k in props:
        de = g.out_lit(fl[[x for x in fl if fl[x]['DE'] == d][0]]['DE'])
        h = hist[s]
        bad = 0
        for j in range(k):
            ch = XOR(h[j], h[j + 1])
            term = AND(v[j + 1], ch) if conv == 0 else OR(v[j + 1] ^ 1, ch)
            bad = OR(bad, term)
        outs.append(AND(de, bad))
    with open(path, 'w') as f:
        f.write(f"aag {nv[0]} {len(inputs)} {len(latches)} {len(outs)} {len(ands)}\n")
        for l in inputs:
            f.write(f"{l}\n")
        for l, n, i in latches:
            f.write(f"{l} {n}\n" if i == 0 else f"{l} {n} {i}\n")
        for o in outs:
            f.write(f"{o}\n")
        for a in ands:
            f.write(f"{a[0]} {a[1]} {a[2]}\n")


def run_pdr(aag, timeout):
    with tempfile.TemporaryDirectory() as td:
        aig = os.path.join(td, 'm.aig')
        from aag2aig import convert
        convert(aag, aig)
        r = subprocess.run(['yosys-abc', '-c', f'read_aiger {aig}; pdr -a -T {timeout} -H {os.environ.get("PDR_H", "0")}'],
                           capture_output=True, text=True)
    return r.stdout


if __name__ == '__main__':
    aagf, mapf, netlist, pairsf, candf, conv, outf = sys.argv[1:8]
    conv = int(conv)
    g = Aig(aagf, mapf)
    fl, grp, _ = groups(netlist, pairsf)
    cand = json.load(open(candf))
    props = []
    for key, k in sorted(cand.items()):
        d, s = key.split('|')
        if k > 0:
            props.append((d, s, k))
    path = outf + '.aag'
    build(g, fl, props, conv, path)
    log = run_pdr(path, int(os.environ.get('PDR_T', '3000')))
    open(outf + '.log', 'w').write(log)
    res = {}
    import re
    for m in re.finditer(r'Output\s+(\d+) was asserted in frame\s+(\d+)', log):
        i = int(m.group(1))
        d, s, k = props[i]
        res[f'{d}|{s}'] = ['fail', int(m.group(2))]
    for i, (d, s, k) in enumerate(props):
        res.setdefault(f'{d}|{s}', ['?', k])
    proved = 'Property proved' in log or re.search(r'proved', log) is not None
    json.dump({'props': [[d, s, k] for d, s, k in props], 'res': res, 'tail': log[-3000:]},
              open(outf, 'w'), indent=0)
    print(log[-1500:])
