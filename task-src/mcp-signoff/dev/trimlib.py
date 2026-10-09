import re,sys
src=open(sys.argv[1]).read()
bad=re.compile(r'lpflow|probe|clkdly|clkbuf|clkinv|dlygate|dlymetal|buf_16|_0\b|conb|einv|ebuf|dlx|dlr|sdf|sedf|dfb|dfs|dfr|dfx|edf|tap|fill|decap|diode|macro|bufbuf|bufinv|ha_|fa_|o2bb2a|a2bb2o|mux2i|mux4|sdlclkp|dlclkp|xnor3|xor3|maj3')
out=[];i=0
for m in re.finditer(r'\n    cell \("([^"]+)"\) \{', src):
    pass
# split at cell boundaries
parts=re.split(r'(?=\n    cell \(")', src)
head=parts[0]; cells=parts[1:]
last=cells[-1]
# last cell contains library closing brace
keep=[]
for c in cells:
    name=re.match(r'\n    cell \("([^"]+)"\)',c).group(1)
    if bad.search(name): continue
    keep.append(c)
res=head+''.join(keep)
if not res.rstrip().endswith('}'): res+='\n}\n'
# ensure closing brace present once
if cells and bad.search(re.match(r'\n    cell \("([^"]+)"\)',last).group(1)): res=res.rstrip()+'\n}\n'
open(sys.argv[2],'w').write(res)
print(len(cells),len(keep))
