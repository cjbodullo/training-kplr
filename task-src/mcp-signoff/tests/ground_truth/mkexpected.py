"""expected edges: every flop/input path keeps setup on the next edge and hold on the
launch edge, except flop -> edfxtp D pin paths, which take the proven multiplier."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tests'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'solution'))
import grade
from netinfo import parse as flops
truth = json.load(open(sys.argv[1]))
fl = flops(sys.argv[3])   # clock-gate-aware model view: gated dfxtp -> enable = GATE net
base, wns = grade.edges(None)
exp = {}
for (mm, s, e), k in base.items():
    assert k == (1 if mm == 'max' else 0), (mm, s, e, k)
    n = 1
    inst, _, pin = e.rpartition('/')
    if s in fl and inst in fl and pin == 'D' and fl[inst]['DE']:
        n = truth[f"{fl[inst]['DE']}|{s}"] + 1
    exp[f'{mm}|{s}|{e}'] = n if mm == 'max' else 0
json.dump(exp, open(sys.argv[2], 'w'), indent=0, sort_keys=True)
import collections
print(len(exp), collections.Counter(exp.values()), 'base wns', wns)
