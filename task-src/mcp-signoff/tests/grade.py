"""grading helpers for the cicd exception set.

parse() checks the agent's sdc against a small whitelist grammar and returns
canonical sdc text, so no agent tcl ever reaches OpenSTA. edges() loads the
frozen netlist with base.sdc plus that text in OpenSTA and reports, for every
timing path from every flop and every input port, the setup capture edge and
the hold check edge in clock periods.
"""
import math
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = '/opt/design' if os.path.isdir('/opt/design') else os.path.join(HERE, 'design')
NET = os.path.join(DESIGN, 'cicd.v')
LIB = os.environ.get('STA_LIB', '/opt/sta/sky130hd_tt.lib')
BASE = os.path.join(DESIGN, 'base.sdc')
PERIOD = 5.5

CMDS = ('set_multicycle_path', 'set_false_path')
FLAGS = ('-setup', '-hold', '-start', '-end')
WORD = re.compile(r'^[A-Za-z0-9_/*?]+$')


class SdcError(Exception):
    pass


def _tokens(line):
    toks, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c.isspace():
            i += 1
            continue
        if c == '[':
            j = line.find(']', i)
            if j < 0:
                raise SdcError('unbalanced [')
            toks.append(line[i:j + 1])
            i = j + 1
            continue
        j = i
        while j < n and not line[j].isspace():
            j += 1
        toks.append(line[i:j])
        i = j
    return toks


def _obj(tok):
    m = re.match(r'^\[\s*(get_cells|get_pins)\s+(\{([^{}]*)\}|([^\s{}\[\]]+))\s*\]$', tok)
    if not m:
        raise SdcError(f'object spec not allowed: {tok}')
    words = (m.group(3) if m.group(3) is not None else m.group(4)).split()
    if not words:
        raise SdcError(f'empty object spec: {tok}')
    for w in words:
        if not WORD.match(w):
            raise SdcError(f'bad name pattern: {w}')
    return m.group(1), words


def parse(text):
    out = []
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if any(ch in line for ch in ';$"\\'):
            raise SdcError(f'line {no}: tcl syntax not allowed')
        toks = _tokens(line)
        cmd = toks[0]
        if cmd not in CMDS:
            raise SdcError(f'line {no}: command not allowed: {cmd}')
        mult, flags, frm, to = None, [], None, None
        k = 1
        while k < len(toks):
            t = toks[k]
            if t in FLAGS:
                if t in flags:
                    raise SdcError(f'line {no}: repeated {t}')
                flags.append(t)
                k += 1
            elif t in ('-from', '-to'):
                if k + 1 >= len(toks):
                    raise SdcError(f'line {no}: {t} without object')
                o = _obj(toks[k + 1])
                if t == '-from':
                    if frm:
                        raise SdcError(f'line {no}: repeated -from')
                    frm = o
                else:
                    if to:
                        raise SdcError(f'line {no}: repeated -to')
                    to = o
                k += 2
            elif re.match(r'^\d+$', t) and cmd == 'set_multicycle_path' and mult is None:
                mult = int(t)
                k += 1
            else:
                raise SdcError(f'line {no}: token not allowed: {t}')
        if cmd == 'set_multicycle_path' and mult is None:
            raise SdcError(f'line {no}: multiplier missing')
        if cmd == 'set_false_path' and ('-start' in flags or '-end' in flags):
            raise SdcError(f'line {no}: -start/-end on set_false_path')
        if not frm and not to:
            raise SdcError(f'line {no}: needs -from or -to')
        parts = [cmd]
        if mult is not None:
            parts.append(str(mult))
        parts += flags
        for opt, o in (('-from', frm), ('-to', to)):
            if o:
                parts.append(f"{opt} [{o[0]} {{{' '.join(o[1])}}}]")
        out.append(' '.join(parts))
    return '\n'.join(out) + '\n'


TCL = r"""
read_liberty {lib}
read_verilog {net}
link_design cicd
read_sdc {base}
{extra}
set out [open {out} w]
set srcs [concat [all_registers -cells] [delete_from_list [all_inputs] [get_ports {{clk rst_n scan_en}}]]]
foreach s $srcs {{
  set sn [get_full_name $s]
  foreach mm {{max min}} {{
    foreach pe [find_timing_paths -from $s -path_delay $mm -group_path_count 1000000 -endpoint_path_count 1 -unique_paths_to_endpoint] {{
      if {{![$pe is_check] && ![$pe is_output_delay]}} continue
      set e [expr {{[$pe target_clk_time] + [$pe target_clk_mcp_adjustment]}}]
      puts $out "$mm $sn [get_full_name [$pe pin]] [sta::format_time $e 4]"
    }}
  }}
}}
close $out
report_worst_slack -max
report_worst_slack -min
"""


def edges(sdc_text):
    """returns ({(mm, src, end): edge_in_periods}, (setup_wns, hold_wns))"""
    with tempfile.TemporaryDirectory() as td:
        extra = ''
        if sdc_text is not None:
            p = os.path.join(td, 'x.sdc')
            open(p, 'w').write(sdc_text)
            extra = f'read_sdc {p}'
        out = os.path.join(td, 'edges.txt')
        tcl = os.path.join(td, 'g.tcl')
        open(tcl, 'w').write(TCL.format(lib=LIB, net=NET, base=BASE, extra=extra, out=out))
        cmd = ['sta', '-no_init', '-exit', tcl]
        if os.geteuid() == 0:
            # OpenSTA reads text derived from the agent's file: run it unprivileged so it
            # cannot reach the root-only answer files under /tests
            os.chmod(td, 0o777)
            for f in os.listdir(td):
                os.chmod(os.path.join(td, f), 0o644)
            cmd = ['setpriv', '--reuid', 'nobody', '--regid', 'nogroup', '--clear-groups'] + cmd
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200, cwd=td)
        if r.returncode != 0 or not os.path.exists(out):
            raise RuntimeError('OpenSTA failed:\n' + r.stdout[-2000:] + r.stderr[-2000:])
        res = {}
        for line in open(out):
            mm, s, e, t = line.split()
            v = float(t)
            if not math.isfinite(v):
                raise RuntimeError(f'non-finite edge time: {line}')
            q = v / PERIOD
            k = round(q)
            if abs(q - k) > 1e-3:
                raise RuntimeError(f'edge not on a clock edge: {line}')
            res[(mm, s, e)] = k
        a = re.search(r'worst slack max (\S+)', r.stdout)
        b = re.search(r'worst slack min (\S+)', r.stdout)
        wns = tuple(x if x is not None and math.isfinite(x) else None
                    for x in (float(a.group(1)) if a else None, float(b.group(1)) if b else None))
    return res, wns
