"""generate a bit parallel C simulator of the mapped netlist AIG.

every 64 bit word carries 64 independent runs. each word gets its own random
stimulus profile. monitors track, for every flop output, how many cycles it
has held its value (age, saturating at 15). for each EDFF enable net g and
each flop S in the D cone of g's flops, the program reports the set of ages
of S seen on cycles where g is high, with the first witness of each age.

usage: gen_sim.py model.aag model.map netlist.v pairs_base.txt out.c out.json
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aig import Aig, groups

aag, mapf, netlist, pairsf, outc, outj = sys.argv[1:7]
g = Aig(aag, mapf)
fl, grp, _ = groups(netlist, pairsf)

srcs = sorted(fl)                          # monitor every flop
sidx = {s: i for i, s in enumerate(srcs)}
des = sorted(grp)
gpairs = [(d, s) for d in des for s in grp[d]]

def lit(l):
    v = f"a[{l >> 1}]"
    return f"(~{v})" if l & 1 else v

# input name -> stimulus expression index
fields = {}
named = {}
for (name, bit), idx in g.inmap.items():
    named[idx] = (name, bit)

C = []
w = C.append
w('#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>')
w(f'#define M {g.M}\n#define NL {len(g.latches)}\n#define NS {len(srcs)}\n#define NP {len(gpairs)}')
w('static inline uint64_t mix(uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}')
w('static inline uint64_t R(uint64_t seed,uint64_t wd,uint64_t cyc,uint64_t f){return mix(seed*0x100000001b3ULL ^ mix(wd*1000003ULL ^ mix(cyc*7919ULL ^ f)));}')
# probability helpers: p = k/16
w('static inline uint64_t P16(uint64_t s,uint64_t wd,uint64_t c,uint64_t f,int k){'
  'if(k<=0)return 0; if(k>=16)return ~0ULL;'
  'uint64_t r0=R(s,wd,c,f*4+0),r1=R(s,wd,c,f*4+1),r2=R(s,wd,c,f*4+2),r3=R(s,wd,c,f*4+3);'
  'uint64_t lt=0,eq=~0ULL; uint64_t rb[4]={r3,r2,r1,r0}; int kb[4]={(k>>3)&1,(k>>2)&1,(k>>1)&1,k&1};'
  'for(int i=0;i<4;i++){uint64_t kk=kb[i]?~0ULL:0; lt|=eq&~rb[i]&kk; eq&=~(rb[i]^kk);} return lt;}')
w('typedef struct {int pv,ps,psel,pen,pwr,paddr_hi,pen0,papply,pdump,pzero,unlock,stall,stall_lo,silent;} prof_t;')
w('static prof_t mkprof(uint64_t s,uint64_t wd){prof_t p; uint64_t r=mix(s^mix(wd*31+7));'
  'int pv[4]={8,12,15,16}; int ps[6]={0,1,2,4,8,12}; int psel[4]={1,2,4,8};'
  'p.pv=pv[r&3]; r>>=2; p.ps=ps[r%6]; r>>=3; p.psel=psel[r&3]; r>>=2; p.pen=8+(r&7); r>>=3;'
  'p.pwr=4+(r&7); r>>=3; p.paddr_hi=(r&3); r>>=2; p.pen0=14+(r&1)*2; r>>=1; p.papply=(r&7)*2; r>>=3;'
  'p.pdump=(r&3)*5; r>>=2; p.pzero=(r&3)*3; r>>=2; p.unlock=(r&3)!=0; r>>=2; p.stall=(r&1); r>>=1; p.stall_lo=(r&1); r>>=1; p.silent=(r&3); return p;}')

w('int main(int argc,char**argv){')
w(' uint64_t seed=strtoull(argv[1],0,10); int NWD=atoi(argv[2]); int NC=atoi(argv[3]); int conv=atoi(argv[4]); int init0=argc>5?atoi(argv[5]):0; int nounlock=argc>6?atoi(argv[6]):0;')
w(' static uint64_t a[M+1]; static uint64_t st[NL]; static uint64_t prev[NS], ag[NS][4];')
w(' static uint64_t seenp[NP][16]; static uint64_t seens[NS][16];')
w(' static int wc[NP][16], ww[NP][16], wb[NP][16];')
w(' memset(seenp,0,sizeof seenp); memset(seens,0,sizeof seens);')
w(' for(int i=0;i<NP;i++)for(int k=0;k<16;k++)wc[i][k]=-1;')
w(' for(int wd=0;wd<NWD;wd++){ prof_t pf=mkprof(seed,wd); if(nounlock) pf.unlock=0;')
w('  memset(st,0,sizeof st);')
for i, (l, nx, ini) in enumerate(g.latches):
    if ini == 1:
        w(f'  st[{i}]=~0ULL;')
w('  for(int c=0;c<NC;c++){ a[0]=0; int pvc=(pf.stall && ((c>>8)&1))?pf.stall_lo:pf.pv; int ul=(pf.unlock && (c==3||c==4)); uint64_t key=(c==3)?0xc1d5:0x2a3e; uint64_t quiet=(pf.silent && ((c>>9)&1))?~0ULL:0;')
# latches into a
for i, (l, nx, ini) in enumerate(g.latches):
    w(f'   a[{l >> 1}]=st[{i}];')
# inputs
for k, l in enumerate(g.inputs):
    if k in named:
        name, bit = named[k]
        if name == 'clk':
            e = '0'
        elif name == 'rst_n':
            e = '(c==0?0ULL:~0ULL)'
        elif name == 'in_valid':
            e = f'P16(seed,wd,c,{k},pvc)'
        elif name == 'sync':
            e = f'P16(seed,wd,c,{k},pf.ps)'
        elif name == 'psel':
            e = f'(ul?~0ULL:P16(seed,wd,c,{k},pf.psel))'
        elif name == 'penable':
            e = f'(ul?~0ULL:P16(seed,wd,c,{k},pf.pen))'
        elif name == 'pwrite':
            e = f'(ul?~0ULL:P16(seed,wd,c,{k},pf.pwr))'
        elif name == 'paddr':
            if bit <= 1:
                e = f'R(seed,wd,c,{k})'
            elif bit == 2:
                e = f'P16(seed,wd,c,{k},pf.paddr_hi*3+2)'
            else:
                e = f'P16(seed,wd,c,{k},pf.paddr_hi)'
        elif name == 'pwdata':
            if bit == 0:
                e = f'P16(seed,wd,c,{k},pf.pen0)'
            elif bit == 1:
                e = f'P16(seed,wd,c,{k},pf.pdump)'
            elif bit == 2:
                e = f'P16(seed,wd,c,{k},pf.papply)'
            else:
                e = f'(R(seed,wd,c,{k}) & ~P16(seed,wd,c,{k+500},pf.pzero))'
        else:
            e = f'R(seed,wd,c,{k})'
    else:
        e = f'R(seed,wd,c,{k})'
    if k in g.initinputs:
        e = f'(init0?0ULL:{e})'
    if k in named and named[k][0] == 'in_data':
        e = f'({e} & ~quiet)'
    if k in named and named[k][0] == 'paddr':
        e = f'(ul?({6 >> named[k][1] & 1}?~0ULL:0):{e})'
    if k in named and named[k][0] == 'pwdata':
        e = f'(ul?(((key>>{named[k][1]})&1)?~0ULL:0):{e})'
    w(f'   a[{l >> 1}]={e};')
for (lhs, r0, r1) in g.ands:
    w(f'   a[{lhs >> 1}]={lit(r0)}&{lit(r1)};')
for i, (l, nx, ini) in enumerate(g.latches):
    w(f'   st[{i}]={lit(nx)};')
# monitors
w('   {')
for s in srcs:
    i = sidx[s]
    q = g.out_lit(fl[s]['Q'])
    w(f'    {{uint64_t cur={lit(q)}; uint64_t ch;'
      f' if(c==0){{ch=0; uint64_t v=conv?0:~0ULL; ag[{i}][0]=ag[{i}][1]=ag[{i}][2]=ag[{i}][3]=v;}}'
      f' else {{ch=cur^prev[{i}];'
      f' uint64_t *A=ag[{i}]; uint64_t sat=A[0]&A[1]&A[2]&A[3]; uint64_t c0=~sat;'
      f' uint64_t n0=A[0]^c0; uint64_t c1=A[0]&c0; uint64_t n1=A[1]^c1; uint64_t c2=A[1]&c1; uint64_t n2=A[2]^c2; uint64_t c3=A[2]&c2; uint64_t n3=A[3]^c3;'
      f' A[0]=n0&~ch; A[1]=n1&~ch; A[2]=n2&~ch; A[3]=n3&~ch;}}'
      f' prev[{i}]=cur;}}')
w('   }')
w('   for(int i=0;i<NS;i++){ uint64_t *A=ag[i]; for(int k=0;k<16;k++){ uint64_t m=~0ULL;'
  ' for(int b=0;b<4;b++){ m&= ((k>>b)&1)?A[b]:~A[b]; } seens[i][k]|=m; } }')
for pi, (d, s) in enumerate(gpairs):
    de = g.out_lit(fl[[x for x in fl if fl[x]['DE'] == d][0]]['DE'])
    w(f'   {{uint64_t de={lit(de)}; if(de){{ uint64_t *A=ag[{sidx[s]}]; for(int k=0;k<16;k++){{ uint64_t m=de;'
      f' for(int b=0;b<4;b++){{ m&= ((k>>b)&1)?A[b]:~A[b]; }} if(m){{ if(wc[{pi}][k]<0){{wc[{pi}][k]=c; ww[{pi}][k]=wd; wb[{pi}][k]=__builtin_ctzll(m);}} seenp[{pi}][k]|=m; }} }} }} }}')
w('  }')
w(' }')
w(' printf("{\\"pairs\\":[");')
w(' for(int i=0;i<NP;i++){ printf("%s[",i?",":""); int f=1; for(int k=0;k<16;k++) if(seenp[i][k]){ printf("%s[%d,%d,%d,%d]",f?"":",",k,wc[i][k],ww[i][k],wb[i][k]); f=0;} printf("]"); }')
w(' printf("],\\"srcs\\":[");')
w(' for(int i=0;i<NS;i++){ printf("%s[",i?",":""); int f=1; for(int k=0;k<16;k++) if(seens[i][k]){ printf("%s%d",f?"":",",k); f=0;} printf("]"); }')
w(' printf("]}\\n"); return 0; }')
open(outc, 'w').write('\n'.join(C) + '\n')
json.dump({'srcs': srcs, 'pairs': gpairs}, open(outj, 'w'))
print(len(srcs), 'sources', len(gpairs), 'group pairs', len(g.ands), 'ands')
