import sys; sys.path.insert(0,'solution')
import fanuc
L={1: 98.412, 2: 110.250, 3: 102.775, 4: 95.300, 5: 124.640, 6: 121.115, 7: 108.880, 8: 101.505, 9: 99.730, 10: 96.210}
# reference frames: block corner left/front/bottom in machine coords
for progs,org in (([1610,1620],None),([1140],(-612,-268,-455)),([2205],(-612,-253,-455))):
    res=fanuc.run_part('environment/data/cnc',progs,L)
    for o,mv in zip(progs,res):
        print('==== O',o)
        o0 = org or ((-610,-290,-425) if o==1610 else (-612,-288,-429))
        f=lambda p: tuple(round(p[i]-o0[i],4) for i in range(3))
        for kind,t,p0,p1,arc in mv:
            if kind!='feed': continue
            if abs(p0[0]-p1[0])<1e-9 and abs(p0[1]-p1[1])<1e-9 and p1[2]<p0[2]:
                print(f'T{t} plunge {f(p1)}')
            elif arc:
                c=arc[0]; print(f'T{t} arc {f(p0)}->{f(p1)} c=({c[0]-o0[0]:.4f},{c[1]-o0[1]:.4f}) ccw={arc[1]}')
