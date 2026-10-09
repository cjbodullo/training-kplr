import subprocess, os, time, signal, json, base64, urllib.request
NAMES = ["m1","m2","m3","m4","m5"]
def peer(i): return f"http://m{i+1}:2380"
def client(i): return f"http://m{i+1}:2379"
def ip(i): return f"127.0.1.{i+1}"
def hosts():
    with open("/etc/hosts", "a") as f:
        for i in range(5): f.write(f"{ip(i)} m{i+1}\n")
class Cluster:
    def __init__(self, root, eto=10000, hb=200):
        self.root=root; self.procs={}
        hosts()
        init=",".join(f"{n}={peer(i)}" for i,n in enumerate(NAMES))
        for i,n in enumerate(NAMES):
            d=f"{root}/{n}"; os.makedirs(d, exist_ok=True)
            log=open(f"{root}/{n}.log","w")
            self.procs[n]=subprocess.Popen(["etcd","--name",n,"--data-dir",f"{d}/data",
              "--listen-peer-urls",f"http://{ip(i)}:2380","--initial-advertise-peer-urls",peer(i),
              "--listen-client-urls",f"http://{ip(i)}:2379","--advertise-client-urls",client(i),
              "--initial-cluster",init,"--initial-cluster-token","tarn-kv-prod","--initial-cluster-state","new",
              "--election-timeout",str(eto),"--heartbeat-interval",str(hb),"--snapshot-count","2000",
              "--log-level","info","--logger","zap"],stdout=log,stderr=subprocess.STDOUT)
    def sig(self,n,s): self.procs[n].send_signal(s)
    def stop(self,n): self.sig(n,signal.SIGSTOP)
    def cont(self,n): self.sig(n,signal.SIGCONT)
    def killall(self):
        for p in self.procs.values(): p.send_signal(signal.SIGKILL)
        for p in self.procs.values(): p.wait()
def b64(s): return base64.b64encode(s.encode()).decode()
def call(i, path, body, timeout=3):
    req=urllib.request.Request(client(i)+path, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
