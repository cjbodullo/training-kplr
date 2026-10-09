import json,sys,re
d=json.load(open(sys.argv[1]))['modules']['cicd']
names={}
for n,v in d['netnames'].items():
    if v.get('hide_name',0): continue
    for i,b in enumerate(v['bits']):
        names.setdefault(b,[]).append((n,i,len(v['bits'])))
out=[];used=set()
for cn,c in d['cells'].items():
    if not re.search(r'df|edf',c['type']): continue
    q=c['connections']['Q'][0]
    cand=[x for x in names.get(q,[]) if not x[0].startswith('_')]
    # prefer reg names that are not port aliases
    cand.sort(key=lambda x:(x[0] in ('out_data','out_tag','prdata','out_valid','ovr'),len(x[0])))
    if not cand: print('NONAME',cn,file=sys.stderr); continue
    n,i,w=cand[0]
    new = f"{n}_reg" if w==1 else f"{n}_reg_{i}_"
    assert new not in used,new; used.add(new)
    out.append(f"rename {cn} {new}")
open(sys.argv[2],"w").write("cd cicd\n"+"\n".join(out)+"\ncd\n")
print(len(out))
