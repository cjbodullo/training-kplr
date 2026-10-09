import json,sys
meta=json.load(open(sys.argv[1])); res=[json.load(open(f)) for f in sys.argv[3:]]
out={}
for i,(d,s) in enumerate(meta['pairs']):
    ks=set()
    for r in res: ks|={x[0] for x in r['pairs'][i]}
    out[f'{d}|{s}']=min(ks) if ks else 15
json.dump(out,open(sys.argv[2],'w'),indent=0)
import collections; print(collections.Counter(out.values()))
