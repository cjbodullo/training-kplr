"""formal model view of the gated netlist: a dfxtp on cg_X_gclk becomes an edfxtp on
clk with DE = that clock gate's GATE net (SCE is scan_en, 0 in mission mode)."""
import re, sys
s = open(sys.argv[1]).read()
gate = {}
for m in re.finditer(r'sky130_fd_sc_hd__sdlclkp_1\s+(\S+)\s*\((.*?)\);', s, re.S):
    pins = dict(re.findall(r'\.(\w+)\(([^)]*)\)', m.group(2)))
    gate[pins['GCLK'].strip()] = pins['GATE'].strip()
def repl(m):
    ind, inst, body = m.group(1), m.group(2), m.group(3)
    pins = dict(re.findall(r'\.(\w+)\(([^)]*)\)', body))
    ck = pins['CLK'].strip()
    if ck not in gate:
        return m.group(0)
    return (f"\n{ind}sky130_fd_sc_hd__edfxtp_1 {inst} (\n{ind}  .CLK(clk),\n{ind}  .D({pins['D'].strip()}),\n"
            f"{ind}  .DE({gate[ck]}),\n{ind}  .Q({pins['Q'].strip()})\n{ind});")
s = re.sub(r'\n(\s*)sky130_fd_sc_hd__dfxtp_1\s+(\S+)\s*\((.*?)\);', repl, s, flags=re.S)
s = re.sub(r'\n\s*sky130_fd_sc_hd__sdlclkp_1\s+\S+\s*\(.*?\);', '', s, flags=re.S)
open(sys.argv[2], 'w').write(s)
print(len(gate), 'gates removed')
