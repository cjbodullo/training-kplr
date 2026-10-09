"""ascii aiger + yosys map reader, and the D-pin source groups from OpenSTA."""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netinfo import parse, wire_of, bit_of


class Aig:
    def __init__(self, aag, mapf):
        L = open(aag).read().split('\n')
        _, M, I, Lc, O, A = L[0].split()
        self.M, I, Lc, O, A = int(M), int(I), int(Lc), int(O), int(A)
        p = 1
        self.inputs = [int(L[p + i]) for i in range(I)]; p += I
        self.latches = []
        for i in range(Lc):
            f = L[p + i].split()
            self.latches.append((int(f[0]), int(f[1]), int(f[2]) if len(f) > 2 else 0))
        p += Lc
        self.outputs = [int(L[p + i]) for i in range(O)]; p += O
        self.ands = []
        for i in range(A):
            a, b, c = map(int, L[p + i].split())
            self.ands.append((a, b, c))
        self.inmap, self.outmap = {}, {}
        self.initinputs = set()
        for line in open(mapf):
            f = line.split()
            if f[0] == 'input':
                self.inmap[(f[3], int(f[2]))] = int(f[1])
            elif f[0] == 'output':
                self.outmap[(f[3], int(f[2]))] = int(f[1])
            elif f[0] == 'init':
                self.initinputs.add(int(f[1]))

    def out_lit(self, net):
        return self.outputs[self.outmap[(wire_of(net), bit_of(net))]]


def groups(netlist, pairs_file):
    """returns flops, {de_net: sorted source instances} for EDFF D pins,
    and the list of (src, dst_pin) pairs."""
    fl = parse(netlist)
    grp = {}
    pairs = []
    for line in open(pairs_file):
        f = line.split()
        if f[0] != 'max':
            continue
        src, end = f[1], f[2]
        inst, pin = end.rsplit('/', 1)
        if inst not in fl or src not in fl:
            continue
        pairs.append((src, end))
        if pin == 'D' and fl[inst]['DE']:
            grp.setdefault(fl[inst]['DE'], set()).add(src)
    return fl, {k: sorted(v) for k, v in grp.items()}, sorted(set(pairs))
