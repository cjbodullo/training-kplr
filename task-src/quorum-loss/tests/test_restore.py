"""grade /app/out/restore.db and /app/out/uncertain.txt against the sealed tarn-kv keyspace.

the snapshot is restored with the real etcdutl 3.5.17 into a throwaway data dir, served by a
local etcd, and read back over the grpc gateway. nothing the agent wrote is executed."""
import base64, json, os, shutil, subprocess, time, urllib.request
import pytest

OUT = "/app/out"
TRUTH = json.load(open("/tests/truth.json"))
WANT = TRUTH["keys"]
WANT_UNCERTAIN = set(TRUTH["uncertain"])
WORK = "/tmp/verify"
URL = "http://127.0.0.1:22379"

def b64(s): return base64.b64encode(s).decode()

@pytest.fixture(scope="session")
def restored():
    db = f"{OUT}/restore.db"
    assert os.path.isfile(db) and not os.path.islink(db), "restore.db missing"
    shutil.rmtree(WORK, ignore_errors=True); os.makedirs(WORK)
    shutil.copyfile(db, f"{WORK}/restore.db")
    r = subprocess.run(["etcdutl", "snapshot", "restore", f"{WORK}/restore.db", "--data-dir", f"{WORK}/data",
                        "--skip-hash-check", "--name", "verify", "--initial-cluster", "verify=http://127.0.0.1:22380",
                        "--initial-advertise-peer-urls", "http://127.0.0.1:22380"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, "etcdutl snapshot restore failed: " + r.stderr[-800:]
    etcd = subprocess.Popen(["etcd", "--name", "verify", "--data-dir", f"{WORK}/data",
                             "--listen-client-urls", URL, "--advertise-client-urls", URL,
                             "--listen-peer-urls", "http://127.0.0.1:22380", "--initial-advertise-peer-urls", "http://127.0.0.1:22380",
                             "--initial-cluster", "verify=http://127.0.0.1:22380"],
                            stdout=open(f"{WORK}/etcd.log", "w"), stderr=subprocess.STDOUT)
    try:
        resp = None
        for _ in range(150):
            try:
                req = urllib.request.Request(URL + "/v3/kv/range", headers={"Content-Type": "application/json"},
                                             data=json.dumps({"key": b64(b"\0"), "range_end": b64(b"\0")}).encode())
                with urllib.request.urlopen(req, timeout=10) as f: resp = json.loads(f.read())
                break
            except Exception:
                time.sleep(0.2)
        assert resp is not None, "restored etcd never served the keyspace"
        got = {}
        for kv in resp.get("kvs", []):
            got[base64.b64decode(kv["key"]).decode("latin-1")] = base64.b64decode(kv.get("value", "")).decode("latin-1")
        assert int(resp.get("count", len(got))) == len(got)
        yield got
    finally:
        etcd.kill(); etcd.wait()

@pytest.fixture(scope="session")
def uncertain():
    p = f"{OUT}/uncertain.txt"
    assert os.path.isfile(p) and not os.path.islink(p), "uncertain.txt missing"
    raw = open(p, "rb").read().decode("latin-1")
    lines = raw.split("\n")
    if lines and lines[-1] == "": lines.pop()
    assert all(l for l in lines), "blank line in uncertain.txt"
    assert len(lines) == len(set(lines)), "duplicate key in uncertain.txt"
    return set(lines)

def test_snapshot_restores(restored):
    assert isinstance(restored, dict)

def test_no_extra_keys(restored):
    extra = sorted(set(restored) - set(WANT))
    assert not extra, f"{len(extra)} keys that should not be in the snapshot, e.g. {extra[:5]}"

def test_no_missing_keys(restored):
    missing = sorted(set(WANT) - set(restored))
    assert not missing, f"{len(missing)} settled keys missing, e.g. {missing[:5]}"

def test_values_exact(restored):
    wrong = sorted(k for k in WANT if k in restored and restored[k] != WANT[k])
    assert not wrong, f"{len(wrong)} keys with the wrong value, e.g. {wrong[:5]}"

def test_uncertain_exact(uncertain):
    over = sorted(uncertain - WANT_UNCERTAIN)
    under = sorted(WANT_UNCERTAIN - uncertain)
    assert not over and not under, f"listed but settled or never existed: {over[:5]}; unsettled but not listed: {under[:5]}"

def test_uncertain_not_restored(restored, uncertain):
    both = sorted(uncertain & set(restored))
    assert not both, f"keys both restored and listed uncertain: {both[:5]}"
