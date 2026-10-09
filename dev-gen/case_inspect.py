"""Print reference layout offsets for items matching a name prefix, plus record bytes."""
import json, sys
sys.path.insert(0, '/root/work/anand_kepler/task-src/copybook-record-decoder/solution')
from unpack.decode import Case, split_records
from unpack.copybook import parse_copybook
from unpack.layout import Layout, walk
c, top = sys.argv[1], sys.argv[2]
rec_no = int(sys.argv[3]) if len(sys.argv) > 3 else 0
case = Case('cases/%s/case.json' % c); recs = parse_copybook(case.copybook); L = Layout(recs)
tbl = L.find(top)
print('record size', [r.size for r in L.records], 'table', top, 'offset', tbl.offset, 'elem', tbl.elem_size, 'occurs', tbl.occurs)
for it in walk(tbl):
    print('  %-28s off=%-5d size=%-4d elem=%-4d %s sync=%s pic=%s' % (it.name, it.offset, it.size, it.elem_size, it.eff_usage, it.sync, it.pic_text))
d = open('cases/%s/data.dat' % c, 'rb').read()
rs = split_records(case, L, d)
r = rs[rec_no]
print('record', rec_no, 'len', len(r))
s = tbl.offset
print(r[s:s + tbl.size].hex(' '))
exp = [json.loads(l) for l in open('cases/%s/expected.jsonl' % c)][rec_no]
def find(o, name):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == name: return v
            f = find(v, name)
            if f is not None: return f
    if isinstance(o, list):
        for v in o:
            f = find(v, name)
            if f is not None: return f
    return None
print('expected', top, json.dumps(find(exp, top))[:400])
