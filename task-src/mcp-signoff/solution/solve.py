"""reference flow for the cicd exception set.

1. OpenSTA lists every flop -> flop pin pair in the frozen netlist.
2. yosys imports the sky130 cell functions and writes the netlist as an AIGER
   model with every flop output and every enable net exposed.
3. for each enable net g and each flop S that reaches a D pin enabled by g,
   abc pdr decides "whenever g is high, S has held its value for the last k
   cycles". k starts at a cap and drops by one for every disproved pair until
   all remaining properties are proved; k+1 is then confirmed disproved.
4. the largest legal multiplier is k+1. emit set_multicycle_path pairs.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from aig import Aig, groups          # noqa: E402
from prove import build, run_pdr     # noqa: E402

NET = '/app/syn/cicd.v'
LIB = '/app/lib/sky130hd_tt.lib'
SDC = '/app/sdc/base.sdc'
OUT = '/app/exceptions.sdc'
WORK = os.environ.get('WORK', '/tmp/mcpwork')
MNET = os.path.join(WORK, 'model_net.v')
CAP = 7


def sh(cmd, **kw):
    print('+', ' '.join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def pairs_file():
    tcl = os.path.join(WORK, 'pairs.tcl')
    out = os.path.join(WORK, 'pairs.txt')
    open(tcl, 'w').write(f"""read_liberty {LIB}
read_verilog {NET}
link_design cicd
read_sdc {SDC}
set out [open {out} w]
foreach c [all_registers -cells] {{
  set cn [get_full_name $c]
  foreach pe [find_timing_paths -from $c -path_delay max -group_path_count 1000000 -endpoint_path_count 1 -unique_paths_to_endpoint] {{
    if {{![$pe is_check]}} continue
    puts $out "max $cn [get_full_name [$pe pin]]"
  }}
}}
close $out
""")
    sh(['sta', '-no_init', '-exit', tcl], stdout=subprocess.DEVNULL)
    return out


def model():
    # the clock gates have no liberty function; model each gated flop as an
    # enable flop on clk whose enable is its gate's GATE net (SCE is scan_en,
    # held at 0 by base.sdc's case analysis)
    sh([sys.executable, os.path.join(HERE, 'unclock.py'), NET, MNET])
    base = os.path.join(WORK, 'model')
    sh([sys.executable, os.path.join(HERE, 'mkmodel.py'), MNET, LIB, base])
    sh(['yosys', '-q', base + '.ys'], stdout=subprocess.DEVNULL)
    return base + '.aag', base + '.map'


def check(g, fl, cand, conv=0):
    props = [(k.split('|')[0], k.split('|')[1], v) for k, v in sorted(cand.items()) if v > 0]
    path = os.path.join(WORK, 'p.aag')
    build(g, fl, props, conv, path)
    log = run_pdr(path, 3000)
    if 'Undecided = 0' not in log:
        raise SystemExit('pdr left properties undecided:\n' + log[-2000:])
    import re
    failed = set()
    for m in re.finditer(r'Output\s+(\d+) was asserted', log):
        d, s, _ = props[int(m.group(1))]
        failed.add(f'{d}|{s}')
    return failed


def main():
    os.makedirs(WORK, exist_ok=True)
    pf = pairs_file()
    aag, mapf = model()
    g = Aig(aag, mapf)
    fl, grp, _ = groups(MNET, pf)
    cand = {f'{d}|{s}': CAP for d in grp for s in grp[d]}
    it = 0
    while True:
        it += 1
        bad = check(g, fl, cand)
        print(f'iteration {it}: {len(bad)} disproved', flush=True)
        if not bad:
            break
        for k in bad:
            cand[k] -= 1
    up = {k: v + 1 for k, v in cand.items()}
    still = set(up) - check(g, fl, up)
    if still:
        raise SystemExit(f'k+1 not disproved for {len(still)} pairs')
    if any(v >= CAP for v in cand.values()):
        raise SystemExit('a pair reached the cap')
    tj = os.path.join(WORK, 'truth.json')
    json.dump(cand, open(tj, 'w'), indent=0)
    sh([sys.executable, os.path.join(HERE, 'emit_sdc.py'), MNET, pf, tj, OUT])


if __name__ == '__main__':
    main()
