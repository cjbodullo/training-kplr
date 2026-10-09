"""build a single-property model, get a pdr counterexample, and decode it."""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aig import Aig, groups
from prove import build
from aag2aig import convert
aagf, mapf, net, pairs, de, src, k, conv = sys.argv[1:9]
g = Aig(aagf, mapf); fl, grp, _ = groups(net, pairs)
build(g, fl, [(de, src, int(k))], int(conv), 'one.aag')
convert('one.aag', 'one.aig')
r = subprocess.run(['yosys-abc', '-c', 'read_aiger one.aig; pdr; write_cex -n one.cex'], capture_output=True, text=True)
print(r.stdout[-400:])
lines = [l.strip() for l in open('one.cex') if l.strip() and not l.startswith('#')]
print(lines[:3])
