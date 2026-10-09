import socket, sys
# minimal: one TAP IR=4 (BYPASS=1111, IDCODE=1110, other -> 8-bit DR)
NEXT = {'TLR':('RTI','TLR'),'RTI':('RTI','SDS'),'SDS':('CDR','SIS'),'CDR':('SDR','E1D'),'SDR':('SDR','E1D'),
 'E1D':('PDR','UDR'),'PDR':('PDR','E2D'),'E2D':('SDR','UDR'),'UDR':('RTI','SDS'),'SIS':('CIR','TLR'),
 'CIR':('SIR','E1I'),'SIR':('SIR','E1I'),'E1I':('PIR','UIR'),'PIR':('PIR','E2I'),'E2I':('SIR','UIR'),'UIR':('RTI','SDS')}
st='TLR'; ir=[1,1,1,0]; irs=[]; drs=[]; tck=0; tms=0; tdi=0; cyc=0; log=[]
def drlen(): return {(1,1,1,1):1,(1,1,1,0):32}.get(tuple(ir),8)
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1); s.bind(('127.0.0.1',int(sys.argv[1]))); s.listen(1)
c,_=s.accept(); f=c.makefile('rwb',buffering=0)
cmds={}
while True:
    b=f.read(1)
    if not b: break
    ch=chr(b[0]); cmds[ch]=cmds.get(ch,0)+1
    if ch in '01234567':
        v=int(ch); ntck=(v>>2)&1; ntms=(v>>1)&1; ntdi=v&1
        if ntck and not tck:
            cyc+=1
            if st=='SIR': irs.append(tdi)
            if st=='SDR': drs.append(tdi)
            if st=='CIR': irs=[]
            if st=='CDR': drs=[]
            st=NEXT[st][tms]
            if st=='UIR': ir=irs[-4:][::-1] if len(irs)>=4 else ir; log.append(('IR',''.join(map(str,irs))))
            if st=='UDR': log.append(('DR',''.join(map(str,drs))))
        tck,tms,tdi=ntck,ntms,ntdi
    elif ch=='R': f.write(b'0')
    elif ch=='Q': break
print('cycles',cyc,'cmds',cmds); print(log[-10:])
