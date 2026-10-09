"""parse the mapped netlist: flop instances, their cell type, Q net, DE net."""
import re
FLOPS = ('sky130_fd_sc_hd__edfxtp_1', 'sky130_fd_sc_hd__dfxtp_1', 'sky130_fd_sc_hd__dfrtp_1')

def parse(path):
    s = open(path).read()
    out = {}
    for m in re.finditer(r'\n\s*(sky130_fd_sc_hd__\w+)\s+(\S+)\s*\((.*?)\);', s, re.S):
        typ, inst, body = m.groups()
        if typ not in FLOPS:
            continue
        pins = dict(re.findall(r'\.(\w+)\(([^)]*)\)', body))
        out[inst] = dict(type=typ, Q=pins['Q'].strip(), D=pins['D'].strip(),
                         DE=pins.get('DE', '').strip() or None)
    return out

def wire_of(net):
    return re.sub(r'\[\d+\]$', '', net)

def bit_of(net):
    m = re.search(r'\[(\d+)\]$', net)
    return int(m.group(1)) if m else 0
