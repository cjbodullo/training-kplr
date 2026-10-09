import json,sys,re,collections
meta=json.load(open(sys.argv[1])); res=[json.load(open(f)) for f in sys.argv[2:]]
def reg(n): return re.sub(r'_reg(_\d+_)?$','',n)
mins={}
for i,(d,s) in enumerate(meta['pairs']):
    ks=set()
    for r in res: ks|={x[0] for x in r['pairs'][i]}
    mins[(d,s)]=min(ks) if ks else None
agg=collections.defaultdict(list)
for (d,s),m in mins.items(): agg[(d,reg(s))].append(m)
for (d,r),v in sorted(agg.items()):
    c=collections.Counter(v)
    print(f"{d:>7} {r:>10}: N={{{', '.join(f'{(k+1) if k is not None else None}:{n}' for k,n in sorted(c.items(),key=lambda x:(x[0] is None,x[0])))}}}")
# constant sources?
for i,s in enumerate(meta['srcs']):
    ks=set()
    for r in res: ks|=set(r['srcs'][i])
    if 0 not in ks: print('NEVER CHANGES?',s,sorted(ks)[:3])
