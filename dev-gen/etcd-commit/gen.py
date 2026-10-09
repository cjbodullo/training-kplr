"""drive a real 5 member etcd 3.5.17 cluster through the tarn-kv outage and keep every member's data dir.

phases
  0 seed keyspace, leases
  1 steady load (all members up)
  2 leader m1 cut off with only m5 (m2 m3 m4 SIGSTOPped): writes append on m1+m5, never commit
  3 m1 m5 stopped, m2 m3 m4 resume, new term, m2 leader; services retry what timed out
  4 m1 resumes (overwritten), heavy load on m1..m4, then SIGKILL everything mid load
evidence later shipped: m4 + m5 data dirs, service call logs. truth: all five dirs.
"""
import json, os, random, signal, subprocess, sys, threading, time, base64, shutil
import urllib.request, urllib.error
from cluster import Cluster, client, call, b64

ROOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/run"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 7
rng = random.Random(SEED)
shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(f"{ROOT}/logs")
IDX = {"m1": 0, "m2": 1, "m3": 2, "m4": 3, "m5": 4}
T0 = time.time()

class Log:
    def __init__(self, name):
        self.f = open(f"{ROOT}/logs/{name}.jsonl", "w"); self.lock = threading.Lock(); self.seq = 0
    def w(self, rec):
        with self.lock:
            self.seq += 1
            rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".%06dZ" % (int(time.time() * 1e6) % 1000000), **rec}
            self.f.write(json.dumps(rec, sort_keys=True) + "\n"); self.f.flush()

def stamp(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%06dZ" % (int(t * 1e6) % 1000000)

def do(log, svc, member, path, body, timeout=2.5):
    t = time.time()
    body = dict(body)
    try:
        r = call(IDX[member], path, body, timeout=timeout)
        log.w({"svc": svc, "sent": stamp(t), "endpoint": client(IDX[member]), "call": path, "req": body, "resp": r})
        return r
    except Exception as e:
        msg = str(e)
        if isinstance(e, urllib.error.HTTPError):
            try: msg = e.read().decode()
            except Exception: pass
        log.w({"svc": svc, "sent": stamp(t), "endpoint": client(IDX[member]), "call": path, "req": body, "error": msg[:300]})
        return None

PH1, PH3, PH4 = 40, 0.8, 0.45
KILL_GAP = float(os.environ.get("KILL_GAP", "0.03"))
BURST_WORKERS, BURST_TASKS, RETRIES = 1000, 6000, 30
c = Cluster(f"{ROOT}/members", eto=10000, hb=150)
time.sleep(8)

def leader():
    for n, i in IDX.items():
        try:
            r = call(i, "/v3/maintenance/status", {}, timeout=1)
            return {v: k for k, v in ids.items()}[r["leader"]]
        except Exception: pass
ids = {}
r = call(0, "/v3/cluster/member/list", {})
for m in r["members"]: ids[m["name"]] = m["ID"]

def move_leader(target):
    for _ in range(20):
        cur = leader()
        if cur == target: return
        if cur:
            subprocess.run(["etcdctl", f"--endpoints={client(IDX[cur])}", "move-leader", "%x" % int(ids[target])],
                           capture_output=True, timeout=20)
        time.sleep(1.5)
    raise SystemExit("could not move leader to " + target)

logs = {s: Log(s) for s in ["inventory", "scheduler", "quota", "registry", "configsvc", "auditor"]}
seqs = {}
def val(svc):
    seqs[svc] = seqs.get(svc, 0) + 1
    return f"{svc}:{seqs[svc]:05d}:{rng.getrandbits(32):08x}"

UP = set(IDX)
M4_BIAS = float(os.environ.get("M4_BIAS", "0"))
SWEEP_P = float(os.environ.get("SWEEP_P", "0.12"))
RUSH = {"on": False}
def pick(rng_, allowed=None):
    pool = sorted(allowed or UP)
    if RUSH["on"] and "m4" in pool and rng_.random() < M4_BIAS:
        return "m4"
    return rng_.choice(pool)

# ---- phase 0: seed
TENANTS = [f"t{n:02d}" for n in range(14)]
HOSTS = [f"h{n:03d}" for n in range(60)]
for h in HOSTS:
    do(logs["inventory"], "inventory", "m1", "/v3/kv/put", {"key": b64(f"/inv/hosts/{h}"), "value": b64(val("inventory"))})
for t in TENANTS:
    do(logs["quota"], "quota", "m2", "/v3/kv/put", {"key": b64(f"/quota/{t}/used"), "value": b64("0")})
    do(logs["quota"], "quota", "m2", "/v3/kv/put", {"key": b64(f"/quota/{t}/limit"), "value": b64(str(rng.choice([50, 80, 120])))})
for k in range(40):
    do(logs["configsvc"], "configsvc", "m3", "/v3/kv/put", {"key": b64(f"/config/flags/f{k:02d}"), "value": b64(val("configsvc"))})
JOBS = {}
for b in range(12):
    for j in range(rng.randint(3, 8)):
        do(logs["scheduler"], "scheduler", "m4", "/v3/kv/put", {"key": b64(f"/jobs/b{b:02d}/j{j}"), "value": b64(val("scheduler"))})
    JOBS[b] = True
# leases: registry services; one batch of instances is let to expire mid run
leases = {}
for g in ["api", "web", "cron"]:
    r = do(logs["registry"], "registry", "m5", "/v3/lease/grant", {"TTL": 20 if g == "cron" else 600})
    leases[g] = r["ID"]
    for n in range(rng.randint(3, 6)):
        do(logs["registry"], "registry", "m5", "/v3/kv/put", {"key": b64(f"/registry/{g}/i{n}"), "value": b64(val("registry")), "lease": leases[g]})

# ---- service behaviour
stop_all = threading.Event()
phase = {"p": 1}
retry_q = []  # timed out writes the owners retry later
rq_lock = threading.Lock()

def quota_bump(rng_, allowed, timeout=2.5):
    t = rng_.choice(TENANTS)
    k = f"/quota/{t}/used"
    m = pick(rng_, allowed)
    r = do(logs["quota"], "quota", m, "/v3/kv/range", {"key": b64(k)}, timeout)
    if not r or not r.get("kvs"): return
    kv = r["kvs"][0]
    cur = int(base64.b64decode(kv["value"]).decode())
    n = rng_.randint(1, 5)
    body = {"compare": [{"key": b64(k), "target": "MOD", "result": "EQUAL", "mod_revision": kv["mod_revision"]}],
            "success": [{"request_put": {"key": b64(k), "value": b64(str(cur + n))}},
                        {"request_put": {"key": b64(f"/quota/{t}/last"), "value": b64(val("quota"))}}],
            "failure": [{"request_put": {"key": b64(f"/quota/{t}/conflicts"), "value": b64(val("quota"))}}]}
    r2 = do(logs["quota"], "quota", m, "/v3/kv/txn", body, timeout)
    if r2 is None:
        with rq_lock: retry_q.append(("quota", t))

def inventory_put(rng_, allowed, timeout=2.5):
    h = rng_.choice(HOSTS)
    m = pick(rng_, allowed)
    if rng_.random() < 0.08:
        # retire a host: drop its record and leave a tombstone note
        body = {"success": [{"request_delete_range": {"key": b64(f"/inv/hosts/{h}")}},
                            {"request_put": {"key": b64(f"/inv/retired/{h}"), "value": b64(val("inventory"))}}]}
        r = do(logs["inventory"], "inventory", m, "/v3/kv/txn", body, timeout)
    else:
        body = {"key": b64(f"/inv/hosts/{h}"), "value": b64(val("inventory"))}
        r = do(logs["inventory"], "inventory", m, "/v3/kv/put", body, timeout)
    if r is None:
        with rq_lock: retry_q.append(("inventory", h))

def scheduler_op(rng_, allowed, timeout=2.5):
    m = pick(rng_, allowed)
    x = rng_.random()
    if x < (SWEEP_P if RUSH["on"] else 0.12):
        b = rng_.randrange(12)
        # sweep a finished batch
        body = {"success": [{"request_delete_range": {"key": b64(f"/jobs/b{b:02d}/"), "range_end": b64(f"/jobs/b{b:02d}0")}},
                            {"request_put": {"key": b64(f"/jobs/sweeps/b{b:02d}"), "value": b64(val("scheduler"))}}]}
        do(logs["scheduler"], "scheduler", m, "/v3/kv/txn", body, timeout)
    elif x < 0.30:
        b = rng_.randrange(12); j = rng_.randrange(9)
        # claim a job only if it still exists (version > 0), else record a miss
        k = f"/jobs/b{b:02d}/j{j}"
        body = {"compare": [{"key": b64(k), "target": "VERSION", "result": "GREATER", "version": "0"}],
                "success": [{"request_put": {"key": b64(k), "value": b64(val("scheduler"))}},
                            {"request_put": {"key": b64(f"/jobs/claims/b{b:02d}"), "value": b64(val("scheduler"))}}],
                "failure": [{"request_put": {"key": b64(f"/jobs/misses/b{b:02d}"), "value": b64(val("scheduler"))}}]}
        do(logs["scheduler"], "scheduler", m, "/v3/kv/txn", body, timeout)
    else:
        b = rng_.randrange(12); j = rng_.randrange(9)
        do(logs["scheduler"], "scheduler", m, "/v3/kv/put", {"key": b64(f"/jobs/b{b:02d}/j{j}"), "value": b64(val("scheduler"))}, timeout)

def config_op(rng_, allowed, timeout=2.5):
    m = pick(rng_, allowed)
    k = rng_.randrange(40)
    do(logs["configsvc"], "configsvc", m, "/v3/kv/put", {"key": b64(f"/config/flags/f{k:02d}"), "value": b64(val("configsvc"))}, timeout)

def auditor_read(rng_, allowed, timeout=2.5):
    m = pick(rng_, allowed)
    pre = rng_.choice(["/inv/", "/quota/", "/jobs/", "/config/"])
    body = {"key": b64(pre), "range_end": b64(pre[:-1] + "0"), "count_only": True}
    if rng_.random() < 0.4: body["serializable"] = True
    do(logs["auditor"], "auditor", m, "/v3/kv/range", body, timeout)

OPS = [(quota_bump, 3), (inventory_put, 4), (scheduler_op, 3), (config_op, 1), (auditor_read, 1)]
def worker(wid, allowed_fn, rate):
    rng_ = random.Random(SEED * 1000 + wid)
    fns = [f for f, w in OPS for _ in range(w)]
    while not stop_all.is_set():
        allowed = allowed_fn()
        if not allowed: time.sleep(0.05); continue
        rng_.choice(fns)(rng_, allowed)
        time.sleep(rng_.expovariate(rate))

def keepalive():
    # api + web leases kept alive; cron left to expire
    while not stop_all.is_set():
        for g in ["api", "web"]:
            m = pick(rng, UP & {"m2", "m3", "m4"} or UP)
            do(logs["registry"], "registry", m, "/v3/lease/keepalive", {"ID": leases[g]}, 1.5)
        time.sleep(3)

def watcher():
    # config reloader: watch /config/ from m3, log every event it sees
    while not stop_all.is_set():
        try:
            body = {"create_request": {"key": b64("/config/"), "range_end": b64("/config0")}}
            req = urllib.request.Request(client(2) + "/v3/watch", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                for line in resp:
                    if stop_all.is_set(): return
                    ev = json.loads(line)
                    logs["configsvc"].w({"svc": "configsvc", "endpoint": client(2), "call": "/v3/watch", "stream": ev})
        except Exception as e:
            time.sleep(0.5)

allowed_now = {"set": set(IDX)}
threads = [threading.Thread(target=worker, args=(w, lambda: allowed_now["set"], 6.0), daemon=True) for w in range(6)]
threads += [threading.Thread(target=keepalive, daemon=True), threading.Thread(target=watcher, daemon=True)]
for t in threads: t.start()

# ---- phase 1: ordinary day
time.sleep(PH1)  # cron lease expires in here
# ---- phase 2: m1 leads, m2 m3 m4 hang (SIGSTOP); writes pile up on m1 + m5 and never commit
allowed_now["set"] = set()
time.sleep(1)
move_leader("m1")
for n in ["m2", "m3", "m4"]: c.stop(n)
UP.difference_update({"m2", "m3", "m4"})
from concurrent.futures import ThreadPoolExecutor
pool = ThreadPoolExecutor(max_workers=BURST_WORKERS)
t_end = time.time() + 7.0  # inside the 10 s election timeout m1 keeps leading and appending
def burst_one(i):
    r_ = random.Random(SEED * 7919 + i)
    if time.time() < t_end:
        r_.choice([quota_bump, inventory_put, inventory_put, scheduler_op, config_op])(r_, {"m1", "m5"})
futs = [pool.submit(burst_one, i) for i in range(BURST_TASKS)]
for f in futs: f.result()
time.sleep(1)
c.stop("m1"); time.sleep(0.4); c.stop("m5")
UP.difference_update({"m1", "m5"})
# ---- phase 3: m2 m3 m4 come back, new term, m2 leads; services retry what timed out
for n in ["m2", "m3", "m4"]: c.cont(n)
UP.update({"m2", "m3", "m4"})
time.sleep(24)
move_leader("m2")
with rq_lock: todo = list(retry_q); retry_q.clear()
rng.shuffle(todo)
for svc, what in todo[:RETRIES]:
    if svc == "quota":
        quota_bump(rng, {"m2", "m3", "m4"})
    elif svc == "inventory":
        do(logs["inventory"], "inventory", rng.choice(["m2", "m3", "m4"]), "/v3/kv/put",
           {"key": b64(f"/inv/hosts/{what}"), "value": b64(val("inventory"))})
allowed_now["set"] = {"m2", "m3", "m4"}
time.sleep(PH3)
# ---- phase 4: m1 rejoins, rush hour, m4 loses power, then the rest
allowed_now["set"] = set()
c.cont("m1"); UP.add("m1")
time.sleep(3)
allowed_now["set"] = {"m1", "m2", "m3", "m4"}
RUSH["on"] = True
more = [threading.Thread(target=worker, args=(100 + w, lambda: allowed_now["set"], 200.0), daemon=True) for w in range(40)]
for t in more: t.start()
time.sleep(PH4 + rng.random() * 0.3)
c.procs["m4"].send_signal(signal.SIGKILL)  # m4's shelf lost power first
time.sleep(KILL_GAP + rng.random() * 0.03)
c.killall()
time.sleep(0.3)
stop_all.set()
time.sleep(3)
json.dump({"ids": ids, "leases": leases, "seed": SEED}, open(f"{ROOT}/meta.json", "w"))
print("done", ROOT)
