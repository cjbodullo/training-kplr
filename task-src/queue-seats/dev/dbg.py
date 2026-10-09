import sys, collections, numpy as np
sys.path.insert(0,'solution'); sys.argv=['x','x','x','/tmp/qsim']
import plan as P
calls, ag = P.parse('dev/hist/queue_log')
bt = collections.defaultdict(list)
for c in calls.values():
    if 'talk' in c and not c['xfer_in']: bt[(c['q'], P.block(c['end']-c['talk']))].append(c['talk'])
for k in sorted(bt): print(k, len(bt[k]), round(np.mean(bt[k]),1))
acw = P.after_call(calls, ag)
for q in acw:
    v=np.array([x for x in acw[q] if x is not None]); print(q, 'acw frac', round((v>0).mean(),3), 'mean span', round(v[v>0].mean(),1), 'after@new', round(np.where(v>0, np.maximum(P.WRAP_NEW[q], v), P.WRAP_NEW[q]).mean(),1))
