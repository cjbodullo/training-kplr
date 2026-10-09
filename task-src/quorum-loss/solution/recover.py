"""reference salvage of tarn-kv: work out the committed keyspace from m4, m5 and the call logs,
then write it into a scratch etcd 3.5.17 and snapshot that."""
import base64, json, os, subprocess, sys, time, urllib.request, shutil
from quorum import analyze

data, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
A = analyze(f"{data}/m4", f"{data}/m5", f"{data}/calls")
present, uncertain = A["present"], A["uncertain"]
print("histories consistent with the evidence:", len(A["worlds"]), "keys:", len(present), "uncertain:", len(uncertain))

scratch = "/tmp/scratch-etcd"
shutil.rmtree(scratch, ignore_errors=True)
url = "http://127.0.0.1:12379"
etcd = subprocess.Popen(["etcd", "--name", "restore", "--data-dir", scratch,
                         "--listen-client-urls", url, "--advertise-client-urls", url,
                         "--listen-peer-urls", "http://127.0.0.1:12380", "--initial-advertise-peer-urls", "http://127.0.0.1:12380",
                         "--initial-cluster", "restore=http://127.0.0.1:12380"],
                        stdout=open("/tmp/scratch-etcd.log", "w"), stderr=subprocess.STDOUT)
def call(path, body):
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())
for _ in range(100):
    try: call("/v3/kv/range", {"key": base64.b64encode(b"x").decode()}); break
    except Exception: time.sleep(0.2)
try:
    for k, v in sorted(present.items()):
        call("/v3/kv/put", {"key": base64.b64encode(k).decode(), "value": base64.b64encode(v).decode()})
    n = int(call("/v3/kv/range", {"key": base64.b64encode(b"\0").decode(), "range_end": base64.b64encode(b"\0").decode(), "count_only": True}).get("count", 0))
    assert n == len(present), (n, len(present))
    if os.path.exists(f"{out}/restore.db"): os.remove(f"{out}/restore.db")
    subprocess.run(["etcdctl", f"--endpoints={url}", "snapshot", "save", f"{out}/restore.db"], check=True)
finally:
    etcd.terminate(); etcd.wait()
with open(f"{out}/uncertain.txt", "w") as f:
    for k in uncertain: f.write(k.decode() + "\n")
