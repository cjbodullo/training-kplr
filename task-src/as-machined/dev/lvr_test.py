import sys; sys.path.insert(0, '/w/solution')
import models, fanuc, cut
(c,) = fanuc.run_part('/w/environment/data/cnc', [2205], models.LENGTH)
stock = models.block(110.0, 45.0, 20.0)
for t in (3, 9):
    r = cut.cut(stock, cut.sweeps([m for m in c if m[1] == t], models.TOOLS))
    print('tool', t, [(s.isValid(), round(s.Volume(), 3)) for s in r.Solids()], flush=True)
r = cut.cut(stock, cut.sweeps(c, models.TOOLS))
print('all', [(s.isValid(), round(s.Volume(), 3)) for s in r.Solids()], flush=True)
