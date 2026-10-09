#!/usr/bin/env python3
"""Deterministic seed data for the reserve-svc catalogue.

Writes catalogue.csv.gz, stock.csv.gz and reservations.csv.gz. Same bytes every
run; the environment and the verifier ship identical copies.
"""
from __future__ import annotations

import csv
import gzip
import os
import random
import sys

SEED = 20260922
N_SKUS = 25000
WAREHOUSES = ["DFW1", "ATL2", "RNO3", "CMH4", "EWR5", "SLC6"]
FAMILIES = [
    ("BOL", "hex bolt"), ("HRN", "wire harness"), ("PMP", "circulation pump"),
    ("VLV", "ball valve"), ("BRG", "roller bearing"), ("GSK", "gasket set"),
    ("FLT", "inline filter"), ("SNS", "pressure sensor"), ("CPL", "shaft coupling"),
    ("MTR", "gear motor"), ("PNL", "control panel"), ("CBL", "control cable"),
    ("SWT", "limit switch"), ("RLY", "power relay"), ("FAN", "axial fan"),
    ("HSE", "hydraulic hose"),
]
GRADES = ["304 stainless", "316 stainless", "zinc plated", "brass", "nitrile",
          "viton", "cast iron", "aluminium", "carbon steel", "ptfe lined"]
SIZES = ['1/4"', '3/8"', '1/2"', '3/4"', '1"', '1 1/4"', '1 1/2"', '2"', "dn25", "dn50",
         "m6", "m8", "m10", "m12", "m16"]
CHANNELS = ["web", "web", "web", "edi", "csr", "marketplace", "wholesale"]


def main(outdir: str) -> int:
    rng = random.Random(SEED)
    os.makedirs(outdir, exist_ok=True)
    rows = []
    used = set()
    for _ in range(N_SKUS):
        fam, noun = rng.choice(FAMILIES)
        while True:
            sku = f"{fam}-{rng.randrange(10000, 99999)}"
            if sku not in used:
                used.add(sku)
                break
        warehouse = rng.choice(WAREHOUSES)
        roll = rng.random()
        klass = "A" if roll < 0.12 else ("B" if roll < 0.45 else "C")
        desc = f"{rng.choice(SIZES)} {noun}, {rng.choice(GRADES)}"
        cost = round(rng.uniform(0.35, 940.0), 2)
        active = rng.random() > 0.015
        rows.append((sku, desc, warehouse, klass, f"{cost:.2f}", "t" if active else "f"))
    rows.sort()

    stock = {}
    for sku, _desc, _wh, klass, _cost, active in rows:
        if active == "f":
            stock[sku] = rng.randrange(0, 40)
            continue
        tail = rng.random()
        if klass == "A":
            if tail < 0.18:
                stock[sku] = rng.randrange(3, 14)
            elif tail < 0.55:
                stock[sku] = rng.randrange(14, 120)
            else:
                stock[sku] = rng.randrange(120, 900)
        elif klass == "B":
            stock[sku] = rng.randrange(0, 260) if tail > 0.12 else rng.randrange(1, 18)
        else:
            stock[sku] = rng.randrange(0, 90)

    # historical ledger: active reservations that never exceed what is on hand,
    # plus a tail of released ones.
    reservations = []
    taken: dict[str, int] = {}
    pool = [r[0] for r in rows if r[5] == "t" and stock[r[0]] >= 4]
    rng.shuffle(pool)
    for i, sku in enumerate(pool[:9000]):
        room = stock[sku] - taken.get(sku, 0)
        if room <= 1:
            continue
        for _ in range(rng.randrange(1, 4)):
            room = stock[sku] - taken.get(sku, 0)
            if room <= 1:
                break
            qty = rng.randrange(1, max(2, min(room, 9)))
            taken[sku] = taken.get(sku, 0) + qty
            state = "active" if rng.random() < 0.72 else "released"
            if state == "released":
                taken[sku] -= qty
            minutes = rng.randrange(20, 60 * 24 * 9)
            reservations.append(
                (sku, qty, state, rng.choice(CHANNELS), f"seed-{i}-{len(reservations)}", minutes)
            )
    rng.shuffle(reservations)

    def dump(name, header, data):
        path = os.path.join(outdir, name)
        with gzip.open(path, "wt", newline="", compresslevel=9) as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(data)
        return path

    dump("catalogue.csv.gz", ["sku", "description", "warehouse", "velocity_class", "unit_cost", "active"], rows)
    dump("stock.csv.gz", ["sku", "on_hand"], [(s, stock[s]) for s, *_ in rows])
    dump("reservations.csv.gz", ["sku", "qty", "state", "channel", "idem_key", "age_minutes"], reservations)

    fast = [r for r in rows if r[3] == "A" and r[2] in ("DFW1", "ATL2") and r[5] == "t"]
    low = [r for r in fast if stock[r[0]] - taken.get(r[0], 0) <= 12]
    print(f"skus={len(rows)} reservations={len(reservations)} fast_lane_skus={len(fast)} "
          f"fast_lane_low_availability={len(low)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
