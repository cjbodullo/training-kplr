#!/usr/bin/env python3
"""Generate the INC-4471 evidence: api access log, metrics scrape, cache stats, ledger rows."""
from __future__ import annotations

import csv, gzip, os, random, sys
from datetime import datetime, timedelta

OUT = sys.argv[1]
CAT = sys.argv[2]
SEED = 4471
rng = random.Random(SEED)

# sku, on_hand, order qty of each of the two admissions, units already reserved
INCIDENT = [("HSE-43140", 9, 6, 0), ("CBL-44477", 6, 2, 4),
            ("PMP-14825", 7, 5, 0), ("MTR-72980", 9, 4, 5)]

skus = []
with gzip.open(os.path.join(CAT, "catalogue.csv.gz"), "rt") as fh:
    for row in csv.DictReader(fh):
        skus.append((row["sku"], row["warehouse"], row["velocity_class"]))
hub_a = [s for s, w, c in skus if c == "A" and w in ("DFW1", "ATL2")]
all_skus = [s for s, _, _ in skus]

T0 = datetime(2026, 9, 18, 2, 0, 0)
CLIENTS = ["10.40.3.18", "10.40.3.19", "10.40.3.22", "10.40.7.4", "10.40.7.5", "10.41.1.60"]


def stamp(t: datetime) -> str:
    return t.strftime("[%d/%b/%Y:%H:%M:%S +0000]")


lines: list[tuple[datetime, str]] = []


def add(t: datetime, method: str, path: str, status: int, size: int, micros: int, ip=None) -> None:
    ip = ip or rng.choice(CLIENTS)
    lines.append((t, f'{ip} {stamp(t)} "{method} {path} HTTP/1.1" {status} {size} {micros}us'))


# health checks every ten seconds
t = T0
while t < T0 + timedelta(minutes=12):
    add(t, "GET", "/healthz", 200, 40, rng.randrange(900, 2600), ip="127.0.0.1")
    t += timedelta(seconds=10)

# night shift storefront traffic
t = T0
while t < T0 + timedelta(minutes=12):
    t += timedelta(milliseconds=rng.randrange(120, 900))
    sku = rng.choice(all_skus)
    add(t, "GET", f"/v1/availability/{sku}", 200, rng.randrange(180, 260), rng.randrange(1100, 9000))
    if rng.random() < 0.18:
        add(t + timedelta(milliseconds=rng.randrange(5, 60)), "GET", f"/v1/skus/{sku}", 200,
            rng.randrange(150, 230), rng.randrange(1400, 7000))

# night shift orders
t = T0
while t < T0 + timedelta(minutes=12):
    t += timedelta(seconds=rng.uniform(1.5, 9.0))
    sku = rng.choice(hub_a)
    ok = rng.random() < 0.86
    add(t, "POST", "/v1/reservations", 201 if ok else 409, rng.randrange(150, 220),
        rng.randrange(4000, 26000))
    if rng.random() < 0.08:
        add(t + timedelta(seconds=rng.uniform(1, 40)), "DELETE",
            f"/v1/reservations/{rng.randrange(310000, 319000)}", 200, 96, rng.randrange(5000, 30000))

# close-out runs, one per warehouse, sequential
close_out = []
t = T0 + timedelta(seconds=3)
for wh, secs in [("DFW1", 214), ("ATL2", 196), ("RNO3", 168), ("CMH4", 151)]:
    close_out.append((wh, t, t + timedelta(seconds=secs)))
    add(t + timedelta(seconds=secs), "POST", "/v1/reports/close-out", 201, 118, secs * 1_000_000,
        ip="10.41.9.2")
    t += timedelta(seconds=secs + rng.randrange(2, 9))

# marketplace catalogue re-sync from 02:05, batches of 500
t = T0 + timedelta(minutes=5)
for i in range(44):
    dur = rng.randrange(310000, 1450000)
    add(t, "POST", "/v1/availability/bulk", 200, rng.randrange(96000, 132000), dur, ip="10.41.4.11")
    t += timedelta(microseconds=dur + rng.randrange(40000, 260000))

# the four pairs: both orders park behind the share lock the atl2 run holds
atl_end = close_out[1][2]
admitted = []
for sku, on_hand, qty, existing in INCIDENT:
    first = atl_end - timedelta(seconds=rng.uniform(24.0, 28.5))
    second = first + timedelta(seconds=rng.uniform(10.0, 19.0))
    for start, ip, channel in ((first, "10.40.3.18", "csr"), (second, "10.40.3.19", "web")):
        done = atl_end + timedelta(milliseconds=rng.randrange(20, 700))
        add(done, "POST", "/v1/reservations", 201, 198,
            int((done - start).total_seconds() * 1_000_000), ip=ip)
        admitted.append((sku, qty, channel, start))

lines.sort(key=lambda r: r[0])
os.makedirs(OUT, exist_ok=True)
with gzip.open(os.path.join(OUT, "api-2026-09-18.log.gz"), "wt", compresslevel=9) as fh:
    for _, line in lines:
        fh.write(line + "\n")

# metrics scrape at 02:06, four workers plus the sweeper
counters = {
    "cache_hits_total": (41000, 52000), "cache_misses_total": (9000, 12000),
    "cache_publish_total": (9000, 12000), "cache_restate_total": (60, 140),
    "admissions_fast_total": (300, 520), "admissions_authoritative_total": (40, 90),
    "admissions_rejected_total": (30, 70), "reservations_created_total": (280, 480),
    "reservations_released_total": (20, 50), "http_requests_total": (52000, 64000),
    "close_out_runs_total": (1, 3),
}
with open(os.path.join(OUT, "metrics-2026-09-18T0206.txt"), "w") as fh:
    fh.write("# scraped from http://127.0.0.1:8080/internal/metrics at 2026-09-18T02:06:04Z\n")
    for pid in (1184, 1185, 1186, 1187):
        fh.write("# reserve-svc worker counters\n")
        for name, (lo, hi) in counters.items():
            fh.write(f'reservesvc_{name}{{pid="{pid}"}} {rng.randrange(lo, hi)}\n')

with open(os.path.join(OUT, "cache-stats-2026-09-18T0206.txt"), "w") as fh:
    fh.write("$ memcstat --servers=/run/reserve/mc/memcached.sock   # 2026-09-18T02:06:11Z\n")
    for k, v in [("uptime", 1893406), ("curr_connections", 27), ("total_items", 1841233),
                 ("curr_items", 7994), ("bytes", 2085512), ("limit_maxbytes", 2097152),
                 ("get_hits", 5992418), ("get_misses", 1836740), ("cmd_set", 1841233),
                 ("evictions", 1833239), ("evicted_unfetched", 1719802), ("expired_unfetched", 0),
                 ("reclaimed", 0), ("threads", 2)]:
        fh.write(f"  {k:<20} {v}\n")

# ledger rows kept for the four skus
with open(os.path.join(OUT, "ledger-INC-4471.txt"), "w") as fh:
    fh.write("reserve=> -- kept 19 September, before the surplus rows were released\n")
    fh.write("reserve=> SELECT r.id, r.sku, r.qty, r.state, r.channel, r.created_at, r.intent_token IS NOT NULL AS fast_lane\n")
    fh.write("reserve->   FROM reservations r WHERE r.sku IN ('HSE-43140','CBL-44477','PMP-14825','MTR-72980')\n")
    fh.write("reserve->    AND r.created_at > '2026-09-18 01:50' ORDER BY r.sku, r.created_at;\n\n")
    fh.write(f"{'id':>8} | {'sku':<10} | qty | state  | channel | created_at                    | fast_lane\n")
    fh.write("-" * 92 + "\n")
    rid = 3141592
    for sku, qty, channel, when in sorted(admitted, key=lambda r: (r[0], r[3])):
        rid += rng.randrange(3, 40)
        fh.write(f"{rid:>8} | {sku:<10} | {qty:>3} | active | {channel:<7} | "
                 f"{when.strftime('%Y-%m-%d %H:%M:%S.%f')}+00 | t\n")
    fh.write("\nreserve=> SELECT sku, on_hand FROM stock WHERE sku IN "
             "('HSE-43140','CBL-44477','PMP-14825','MTR-72980');\n\n")
    for sku, on_hand, _, _ in INCIDENT:
        fh.write(f"  {sku:<10} | {on_hand}\n")
    fh.write("\nreserve=> SELECT sku, count(*) FILTER (WHERE settled_at IS NOT NULL) AS settled,\n")
    fh.write("reserve->        count(*) FILTER (WHERE expired_at IS NOT NULL) AS expired\n")
    fh.write("reserve->   FROM admission_intents WHERE created_at > '2026-09-18 02:00'\n")
    fh.write("reserve->    AND created_at < '2026-09-18 02:12' GROUP BY sku ORDER BY 2 DESC LIMIT 8;\n\n")
    fh.write(f"{'sku':<10} | settled | expired\n" + "-" * 32 + "\n")
    for sku in [s for s, _, _, _ in INCIDENT] + rng.sample(hub_a, 4):
        fh.write(f"{sku:<10} | {rng.randrange(2, 9):>7} | {0:>7}\n")

print("evidence written to", OUT)
