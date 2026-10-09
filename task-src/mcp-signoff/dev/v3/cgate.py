"""clock gate insertion: every edfxtp enable group of MIN or more flops gets one
sky130 sdlclkp (scan clock gate) driven by the group's enable, SCE on scan_en,
and the flops become dfxtp on the gated clock."""
import re, sys, collections
src, dst = sys.argv[1], sys.argv[2]
MIN = 4
s = open(src).read()
inst_re = re.compile(r'\n(\s*)sky130_fd_sc_hd__edfxtp_1\s+(\S+)\s*\((.*?)\);', re.S)
groups = collections.defaultdict(list)
for m in inst_re.finditer(s):
    pins = dict(re.findall(r'\.(\w+)\(([^)]*)\)', m.group(3)))
    groups[pins['DE'].strip()].append(m.group(2))
gated = {de: insts for de, insts in groups.items() if len(insts) >= MIN}
name = {}
used = set()
for de, insts in sorted(gated.items(), key=lambda x: sorted(x[1])[0]):
    base = re.sub(r'_reg(_\d+_)?$', '', sorted(insts)[0])
    n = f'cg_{base}'
    k = 1
    while n in used:
        k += 1; n = f'cg_{base}_{k}'
    used.add(n); name[de] = n
def repl(m):
    ind, inst, body = m.group(1), m.group(2), m.group(3)
    pins = dict(re.findall(r'\.(\w+)\(([^)]*)\)', body))
    de = pins['DE'].strip()
    if de not in gated:
        return m.group(0)
    return (f"\n{ind}sky130_fd_sc_hd__dfxtp_1 {inst} (\n{ind}  .CLK({name[de]}_gclk),\n"
            f"{ind}  .D({pins['D'].strip()}),\n{ind}  .Q({pins['Q'].strip()})\n{ind});")
s = inst_re.sub(repl, s)
# ports
s = s.replace('module cicd(clk, rst_n,', 'module cicd(clk, rst_n, scan_en,', 1)
s = s.replace('  input clk;', '  input clk;\n  input scan_en;', 1)
cg = []
for de, n in sorted(name.items(), key=lambda x: x[1]):
    cg.append(f"  wire {n}_gclk;\n  sky130_fd_sc_hd__sdlclkp_1 {n} (\n    .CLK(clk),\n    .GATE({de}),\n"
              f"    .SCE(scan_en),\n    .GCLK({n}_gclk)\n  );")
s = s.replace('\nendmodule', '\n' + '\n'.join(cg) + '\nendmodule', 1)
open(dst, 'w').write(s)
print(len(gated), 'clock gates', sum(len(v) for v in gated.values()), 'flops gated;',
      sum(len(v) for de, v in groups.items() if de not in gated), 'edfxtp kept')
print({n: len(gated[de]) for de, n in name.items()})
