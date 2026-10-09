import sys, time; sys.path.insert(0, '/w/solution')
import models, fanuc, cut
(c,) = fanuc.run_part('/w/environment/data/cnc', [2205], models.LENGTH)
stock = models.block(110.0, 45.0, 20.0)
def show(tag, r):
    ss = [s for s in r.Solids() if abs(s.Volume()) > 1e-6]
    print(tag, len(r.Solids()), [(s.isValid(), round(s.Volume(), 3)) for s in ss][:8], flush=True)
t9 = cut.sweeps([m for m in c if m[1] == 9], models.TOOLS)
t = time.time(); cut.FUZZY = 0.0; show('nofuzzy', cut.cut(stock, t9)); print(time.time()-t)
cut.FUZZY = 1e-5
t = time.time(); r = stock
for k, s in enumerate(t9):
    r = cut.cut(r, [s])
    ss = [x for x in r.Solids() if abs(x.Volume()) > 1e-6]
    if len(ss) != 1 or not ss[0].isValid():
        print('seq breaks at', k, [round(x.Volume(), 3) for x in ss][:5], flush=True); break
    r = ss[0]
show('seq', r); print(time.time()-t)
