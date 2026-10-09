#!/usr/bin/env python3
"""Ablations and adversarial attempts against reserve-svc.

Each mode drops or changes one ingredient of the reference sequence, or tries a
different attack entirely. Run inside the stack container:

    python3 ablate.py <mode>
"""
from __future__ import annotations

import json, os, random, sys, threading, time, urllib.error, urllib.request

BASE = os.environ.get("SVC_URL", "http://127.0.0.1:8080").rstrip("/")
STAMP = str(int(time.time() * 1000))
TARGET_CANDIDATES = ["BRG-49573", "BOL-24779", "BRG-26098", "BOL-75173", "BOL-17612"]


def call(m, p, b=None, t=180):
    d = json.dumps(b).encode() if b is not None else None
    h = {"Content-Type": "application/json"} if b is not None else {}
    r = urllib.request.Request(BASE + p, data=d, headers=h, method=m)
    try:
        with urllib.request.urlopen(r, timeout=t) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)[:80]}


def pick(lo=2, hi=9, candidates=None):
    for sku in candidates or TARGET_CANDIDATES:
        s, b = call("GET", f"/v1/availability/{sku}")
        if s == 200 and lo <= int(b.get("avail", 0)) <= hi:
            return sku, int(b["avail"])
    raise SystemExit("no suitable sku")


def catalogue(n):
    out, cur = [], ""
    while len(out) < n:
        s, b = call("GET", f"/v1/skus?after={cur}&limit=500")
        if s != 200 or not b.get("skus"):
            break
        out += b["skus"]
        cur = b["next"]
    return out


def flood(names, target, threads=3, poll=False):
    batches = [[s for s in names[i:i+500] if s != target] for i in range(0, len(names), 500)]
    lock, queue = threading.Lock(), list(batches)
    stop = threading.Event()

    def drain():
        while not stop.is_set():
            with lock:
                if not queue:
                    return
                batch = queue.pop()
            call("POST", "/v1/availability/bulk", {"skus": batch})

    ws = [threading.Thread(target=drain, daemon=True) for _ in range(threads)]
    for w in ws:
        w.start()
    if poll:
        while any(w.is_alive() for w in ws):
            call("GET", f"/v1/availability/{target}")
            time.sleep(0.4)
    for w in ws:
        w.join(timeout=90)


def reserve_async(sku, qty, tag, out):
    def go():
        out[tag] = call("POST", "/v1/reservations",
                        {"sku": sku, "qty": qty, "idem_key": f"abl-{STAMP}-{tag}", "channel": "csr"})
    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t


def report_async(payload=None):
    out = {}
    def go():
        out["r"] = call("POST", "/v1/reports/close-out", payload or {}, t=300)
    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t, out


def mode_reference(park=True, evict=True, poll=False, qty_override=None, candidates=None):
    sku, avail = pick(candidates=candidates)
    qty = qty_override or avail
    names = catalogue(12000) if evict else []
    rt = None
    if park:
        rt, _ = report_async()
        time.sleep(0.8)
    out = {}
    t1 = reserve_async(sku, qty, "a", out)
    time.sleep(0.7)
    if evict:
        flood(names, sku, poll=poll)
        call("GET", f"/v1/availability/{sku}")
    s2, b2 = call("POST", "/v1/reservations",
                  {"sku": sku, "qty": qty, "idem_key": f"abl-{STAMP}-b", "channel": "csr"})
    t1.join(timeout=200)
    if rt:
        rt.join(timeout=300)
    print(f"sku={sku} qty={qty} first={out.get('a', (0, {}))[0]} second={s2} {b2.get('error','')}")


def mode_hammer():
    skus = [s for s in catalogue(3000)]
    random.seed(7)
    fast = []
    for sku in random.sample(skus, 40):
        s, b = call("GET", f"/v1/availability/{sku}")
        if s == 200 and b.get("velocity_class") == "A" and b.get("warehouse") in ("DFW1", "ATL2"):
            fast.append((sku, int(b["avail"])))
    if not fast:
        fast = [(pick()[0], 4)]
    n = [0]
    lock = threading.Lock()

    def worker(k):
        while True:
            with lock:
                if n[0] >= 220:
                    return
                n[0] += 1
                i = n[0]
            sku, avail = random.choice(fast)
            qty = random.choice([1, 2, 3, 4, 9, 12, 25])
            call("POST", "/v1/reservations",
                 {"sku": sku, "qty": qty, "idem_key": f"ham-{STAMP}-{k}-{i}", "channel": "web"})

    ws = [threading.Thread(target=worker, args=(k,), daemon=True) for k in range(12)]
    for w in ws:
        w.start()
    for w in ws:
        w.join(timeout=200)
    print(f"hammered {n[0]} reservations over {len(fast)} fast lane skus")


def mode_mixed():
    """race the fast lane against the authoritative lane on the same sku"""
    sku, avail = pick(lo=10, hi=40, candidates=None) if False else pick(lo=4, hi=9)
    for i in range(40):
        out = {}
        t = reserve_async(sku, 12, f"big{i}", out)
        call("POST", "/v1/reservations",
             {"sku": sku, "qty": 2, "idem_key": f"mix-{STAMP}-{i}", "channel": "web"})
        t.join(timeout=60)
    print("mixed lane race done")


def mode_adjust():
    sku, avail = pick()
    call("POST", "/v1/reservations", {"sku": sku, "qty": avail, "idem_key": f"adj-{STAMP}", "channel": "web"})
    s, b = call("POST", "/v1/adjustments", {"sku": sku, "delta": -avail - 5, "reason": "shrink"})
    print(f"adjust below pledged -> {s} {b.get('error','')}")


MODES = {
    "reference": lambda: mode_reference(),
    "no_park": lambda: mode_reference(park=False),
    "no_evict": lambda: mode_reference(evict=False),
    "poll_target": lambda: mode_reference(poll=True),
    "big_qty": lambda: mode_reference(qty_override=12),
    "cold_class": lambda: mode_reference(candidates=["BOL-10000", "BOL-10005", "BOL-10025", "BOL-10037"]),
    "hammer": mode_hammer,
    "mixed": mode_mixed,
    "adjust": mode_adjust,
}

if __name__ == "__main__":
    MODES[sys.argv[1]]()
