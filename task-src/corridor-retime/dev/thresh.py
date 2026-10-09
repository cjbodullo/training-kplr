import re, sys
DD, BB = int(sys.argv[2]), int(sys.argv[3])
cur=None; agg={}
for f in sys.argv[1].split(","):
    for l in open(f):
        if l.startswith('=='): cur=l.split()[1]; agg[cur]=[]; continue
        m=re.search(r'tele (\d+) arr (\d+)/(\d+) dd (\d+) bbmaxlink (\d+)', l)
        if m: agg[cur].append(tuple(int(x) for x in m.groups()))
for k,v in agg.items():
    fails=sum(1 for t,a,n,dd,bb in v if t>0 or a<n or dd>DD or bb>BB)
    print(f"{k:45s} fail {fails}/{len(v)}  dd {sorted(x[3] for x in v)}")
