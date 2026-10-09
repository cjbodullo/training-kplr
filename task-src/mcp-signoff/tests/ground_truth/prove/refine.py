"""iterate: prove candidate k for every pair; any disproved pair drops to k-1; repeat.
then confirm k+1 is disproved for every pair. writes truth.json {g|S: minage}."""
import json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
aag, mapf, net, pairs, cand0, conv, out = sys.argv[1:8]
cand = json.load(open(cand0))
it = 0
while True:
    it += 1
    json.dump(cand, open(f'{out}.cand{it}.json', 'w'))
    subprocess.run([sys.executable, f'{here}/prove.py', aag, mapf, net, pairs, f'{out}.cand{it}.json', conv, f'{out}.pr{it}.json'], check=True, capture_output=True)
    r = json.load(open(f'{out}.pr{it}.json'))
    bad = [k for k, v in r['res'].items() if v[0] != '?']
    und = 'Undecided = 0' not in open(f'{out}.pr{it}.json.log').read()
    print('iter', it, 'disproved', len(bad), 'undecided?', und, flush=True)
    assert not und
    if not bad:
        break
    for k in bad:
        cand[k] -= 1
up = {k: v + 1 for k, v in cand.items()}
json.dump(up, open(f'{out}.up.json', 'w'))
subprocess.run([sys.executable, f'{here}/prove.py', aag, mapf, net, pairs, f'{out}.up.json', conv, f'{out}.upr.json'], check=True, capture_output=True)
r = json.load(open(f'{out}.upr.json'))
notdis = [k for k, v in r['res'].items() if v[0] != 'fail']
print('k+1 not disproved:', len(notdis))
assert not notdis, notdis[:5]
json.dump(cand, open(out, 'w'), indent=0)
