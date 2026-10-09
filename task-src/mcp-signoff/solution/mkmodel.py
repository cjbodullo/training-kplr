import sys
sys.path.insert(0, sys.path[0])
from netinfo import parse, wire_of
fl = parse(sys.argv[1])
wires = sorted({wire_of(v['Q']) for v in fl.values()} | {wire_of(v['DE']) for v in fl.values() if v['DE']})
ys = f"""read_liberty -ignore_miss_func {sys.argv[2]}
read_verilog {sys.argv[1]}
hierarchy -top cicd
cd cicd
expose {' '.join('w:'+w for w in wires)}
cd
flatten
opt_clean
async2sync
dffunmap
opt_clean
techmap
opt_expr
opt_clean
dffunmap
aigmap
opt_clean
write_aiger -ascii -map {sys.argv[3]}.map -zinit {sys.argv[3]}.aag
"""
open(sys.argv[3] + '.ys', 'w').write(ys)
