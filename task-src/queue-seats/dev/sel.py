import sys, collections, datetime as dt, numpy as np
sys.path.insert(0,'solution'); sys.path.insert(0,'dev'); sys.argv=['x','x','x','/tmp/qsim']
import plan as P, world as W
calls = P.load_calls(sys.argv[0] if False else 'dev/hist2/queue_log')
st = collections.defaultdict(lambda: collections.defaultdict(list))
ent=collections.Counter(); ab=collections.Counter()
for c in calls:
    if c.get('xfer_in') or 'enter' not in c: continue
    ent[c['q']]+=1
    if 'aband' in c and c['aband']>=10: ab[c['q']]+=1
    if 'talk' not in c or c.get('xfer'): continue
    b = P.block(c['end']-c['talk'])
    st[(c['q'],b)]['all'].append(c['talk'])
    if c['hold'] - c['ring'] <= 1: st[(c['q'],b)]['nowait'].append(c['talk'])
for q in W.QUEUES: print(q,'abandon>=10s',round(ab[q]/ent[q],3))
for k in sorted(st):
    q,b=k; blk=b.split('_')[-1]; mon=b.startswith('mon')
    m = W.BLOCK_F[q][blk] * (W.MONDAY_TALK[q] if mon else 1)
    qs=W.QUICK_SHARE[q]; true = m*(qs*W.TYPE_TALK[q]['quick'][0]+(1-qs)*W.TYPE_TALK[q]['complex'][0])
    a=st[k]['all']; n=st[k]['nowait']
    print(k, 'true',round(true), 'naive',round(np.mean(a)),f"(+{100*(np.mean(a)/true-1):.0f}%)", 'nowait',round(np.mean(n)) if n else None, len(n))
