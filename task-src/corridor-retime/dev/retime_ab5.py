"""reference am peak retime for the corridor, from the utc loop export only.

usage: retime.py <data dir> <existing.add.xml> <out.add.xml> [docs dir]
"""
import collections
import csv
import statistics
import sys
import xml.etree.ElementTree as ET

import os
DATA, EXISTING, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
AB = set(os.environ.get("AB", "").split(","))
DOCS = sys.argv[4] if len(sys.argv) > 4 else "/app/docs"

SAT = 1950.0        # veh/h of green per lane, measured from saturated discharge in the model
SAT_SIDE = 1750.0   # single lane side roads (turning traffic)
C = 120             # common cycle, the controller maximum
AMBER, ALL_RED, RED_AMBER = 3, 2, 2
INTER = AMBER + ALL_RED + RED_AMBER
PED = 9
MIN_G = {"J1": [10, 7, 9], "J2": [10, 7, 9], "J3": [10, 7, 9], "J4": [10, 7]}
OFFSETS = {"J1": 0, "J2": 112, "J3": 0, "J4": 0}
J4_FOLLOW = 3       # j4 main road green = j3 main road green + this (60 m link)

# ---------------------------------------------------------------- load
chan = {}
for r in csv.DictReader(open(f"{DATA}/channels.csv")):
    chan[(r["site"], r["channel"])] = r
series = collections.defaultdict(dict)       # (site, ch) -> {(date, minute): (count, occ)}
for r in csv.DictReader(open(f"{DATA}/utc_counts.csv")):
    hh, mm = r["period_start"].split(":")
    series[(r["site"], r["channel"])][(r["date"], int(hh) * 60 + int(mm))] = (int(r["count"]), float(r["occupancy_pct"]))
dates = sorted({d for s in series.values() for d, _ in s})
minutes = sorted({m for s in series.values() for _, m in s})


def find(site, approach_prefix, lane_prefix, loop):
    hits = [k for k, r in chan.items() if k[0] == site and r["approach"].startswith(approach_prefix)
            and r["lane"].startswith(lane_prefix) and r["loop"] == loop]
    assert len(hits) == 1, (site, approach_prefix, lane_prefix, loop, hits)
    return hits[0]


def daily(k, d):
    return [series[k].get((d, m), (0, 0.0)) for m in minutes]


# the old plan, as it ran through the whole history
_old = {tl.get("id"): [int(float(p.get("duration"))) for p in tl.iter("phase")]
        for tl in ET.parse(EXISTING).getroot().iter("tlLogic")}
OLD_CYCLE = {j: sum(v) for j, v in _old.items()}
OLD_GREEN = {j: v[0::4] for j, v in _old.items()}      # stage greens (each followed by 3 interstage phases)

# ---------------------------------------------------------------- faults
# 1. stuck loops: count 0 with occupancy pinned at 100 -> those days are void for that channel
void = collections.defaultdict(set)
for k, s in series.items():
    for d in dates:
        v = daily(k, d)
        if all(n == 0 and o >= 99.0 for n, o in v):
            void[k].add(d)

# 2. half term: the school road empties out. use the school road upstream loop (nothing else feeds it)
school_up = find("J3", "School Lane", "single", "upstream")
peak_school = {d: max(n for n, _ in daily(school_up, d)) for d in dates}
med = statistics.median(peak_school.values())
term = [d for d in dates if peak_school[d] > 0.5 * med]
print("half term (excluded):", [d for d in dates if d not in term])

# 3. swapped feeders at J3: the channel listed as the school road stop line carries more traffic than
# the school stage can physically discharge under the old plan, and its shape is the
# westbound main road's. the listed westbound nearside channel carries the school road's shape.
school_sl = find("J3", "School Lane", "single", "stop line")
wb3_near = find("J3", "A-road westbound", "nearside", "stop line")


def peak_hour(k, days):
    tot = [0.0] * len(minutes)
    used = [d for d in days if d not in void[k]]
    for d in used:
        for i, (n, _) in enumerate(daily(k, d)):
            tot[i] += n
    tot = [t / len(used) for t in tot]
    return max(sum(tot[i:i + 12]) for i in range(len(tot) - 11))


old_school_cap = OLD_GREEN["J3"][1] / OLD_CYCLE["J3"] * SAT_SIDE
if "swap" not in AB and peak_hour(school_sl, term) > 1.3 * old_school_cap and peak_hour(wb3_near, term) < peak_hour(school_up, term) * 1.3:
    print("J3: school road stop line and westbound nearside feeders are crossed, swapping back")
    series[school_sl], series[wb3_near] = series[wb3_near], series[school_sl]

# 4. double counting loop at J2 westbound nearside: J2 westbound stop line total must equal what J3
# sends west (J3 westbound stop lines + school road right turners). per lane, a loop counting twice
# shows a count/occupancy ratio twice its neighbour's.
wb2 = [find("J2", "A-road westbound", "nearside", "stop line"), find("J2", "A-road westbound", "offside", "stop line")]
wb3 = [wb3_near, find("J3", "A-road westbound", "offside", "stop line")]
school_total = peak_hour(school_sl, term)
mcc = list(csv.DictReader(open(f"{DATA}/mcc_J3_2026-10-28.csv")))
sch_out = collections.Counter()
for r in mcc:
    if r["from_arm"] == "School Lane":
        sch_out[r["to_arm"]] += int(r["cars"])
west_share = sch_out["A-road west arm"] / max(1, sum(sch_out.values()))
expect = sum(peak_hour(k, term) for k in wb3) + west_share * school_total
seen = sum(peak_hour(k, term) for k in wb2)
print(f"J2 westbound: stop lines {seen:.0f}/h vs J3 outflow {expect:.0f}/h")
if "double" not in AB and seen > 1.25 * expect:
    ratio = {}
    for k in wb2:
        n = sum(n for d in term for n, o in daily(k, d))
        o = sum(o for d in term for n, o in daily(k, d))
        ratio[k] = n / max(o, 1e-9)
    bad = max(ratio, key=ratio.get)
    print("J2: double counting loop", bad, "halving")
    for key, (n, o) in list(series[bad].items()):
        series[bad][key] = (n / 2.0, o)

# ---------------------------------------------------------------- demand
# orchard way phase 2 was occupied from the start of november, and the plan is for traffic as it is now.
# the estate's morning totals step up in the last week; only those days describe today's demand.
est_sl = [find("J2", "Orchard Way", "nearside", "stop line"), find("J2", "Orchard Way", "offside", "stop line")]
est_total = {d: sum(n for k in est_sl for n, _ in daily(k, d)) for d in term}
base = statistics.median(est_total.values())
now = [d for d in term if est_total[d] > 1.3 * base]
_PRE = [d for d in term if d not in now]
_ALL = list(term)
assert now and now == sorted(term)[-len(now):], ("expected the step change at the end of the history", est_total)
print("days after the estate step change:", now, f"(estate morning totals x{statistics.mean(est_total[d] for d in now) / statistics.mean(est_total[d] for d in term if d not in now):.2f})")

# commuter shape from approaches that never queue back over their upstream loop
ups = [k for k, r in chan.items() if r["loop"] == "upstream" and k != school_up]


def mean_curve(k, days):
    used = [d for d in days if d not in void[k]]
    out = [0.0] * len(minutes)
    for d in used:
        for i, (n, _) in enumerate(daily(k, d)):
            out[i] += n / len(used)
    return out


def occ_curve(k, days):
    used = [d for d in days if d not in void[k]]
    out = [0.0] * len(minutes)
    for d in used:
        for i, (_, o) in enumerate(daily(k, d)):
            out[i] += o / len(used)
    return out


free = [k for k in ups if max(occ_curve(k, term)) < 30.0]
shape = [sum(v) for v in zip(*[mean_curve(k, term) for k in free])]


def half_hour_peak(curve):
    return max(sum(curve[i:i + 6]) for i in range(len(curve) - 5)) * 2


def upstream_of(k):
    r = chan[k]
    up = [u for u in ups if u[0] == k[0] and chan[u]["approach"] == r["approach"] and chan[u]["lane"] == r["lane"]]
    return up[0] if up else None


capped = {}     # lane -> (demand through the junction, counted) for lanes that discharged at capacity

# the orchard way bus gate camera ran on warnings in the phase 2 week. while the estate queue stood,
# eastbound estate drivers cut through it onto Fenwick Road and joined at J1. fines start after the
# history, so those drivers turn right out of Orchard Way at J2 again: they are estate demand that the
# J2 loops never saw, and Fenwick Road demand that will not be there.
gate = collections.Counter()
for r in csv.DictReader(open(f"{DOCS}/orchard_way_bus_gate_BG1.csv")):
    if r["date"] in now:
        hh, mm, _ = r["time"].split(":")
        gate[int(hh) * 60 + int(mm) - (int(hh) * 60 + int(mm)) % 5] += 1
div_total = 0 if ("nogate" in AB or "pre" in AB or "mean" in AB or "ta" in AB) else sum(gate.values()) / len(now)
if div_total == 0:
    gate.clear()
print(f"bus gate: {div_total:.0f} cars a morning cut through in the phase 2 week")
EST_RIGHT = find("J2", "Orchard Way", "offside", "stop line")
FENWICK = find("J1", "Fenwick Road", "single", "stop line")


DD = _PRE if ("pre" in AB or "ta" in AB) else (_ALL if "mean" in AB else now)


def lane_peak(k):
    """peak hourly demand of a stop line lane, today. a lane whose upstream loop saw a standing queue was
    discharging at capacity, so its demand comes from conservation: everything counted over the
    morning arrived over the morning, in the commuter shape."""
    up = upstream_of(k)
    lane = k
    if all(d in void[k] for d in DD):          # dead stop line loop: the upstream loop sees the same lane
        k = up
    curve = mean_curve(k, DD)
    total = sum(curve)
    if lane == EST_RIGHT:
        total += div_total                       # back from the bus gate
    if lane == FENWICK and "estonly" not in AB:
        total -= div_total                       # gone from Fenwick Road
        curve = [c - gate.get(m, 0) / len(now) for c, m in zip(curve, minutes)]
    if up and max(occ_curve(up, DD)) > 30.0:
        rate = half_hour_peak(shape) * total / sum(shape)
        through = half_hour_peak(shape) * sum(mean_curve(k, now)) / sum(shape)
        capped[lane] = (through, half_hour_peak(mean_curve(k, now)))
        r = chan[lane]
        print(f"{lane[0]} {r['approach']} {r['lane']}: queued over its upstream loop, conservation estimate {rate:.0f}/h"
              f" (stop line peak {half_hour_peak(mean_curve(k, now)):.0f}/h)")
        return rate
    return half_hour_peak(curve)


def stop_lines(site, approach):
    return [k for k, r in chan.items() if k[0] == site and r["approach"].startswith(approach) and r["loop"] == "stop line"]


def lane_flows(site, approach):
    return [lane_peak(k) for k in stop_lines(site, approach)]


est = lane_flows("J2", "Orchard Way")
if "ta" in AB:
    est = [est[0] + 29, est[1] + 67]
# saturation flow of the estate's turning lanes, from the capped lane's discharge under the old green
cap_lane = [k for k in capped if k == EST_RIGHT]
SAT_EST = SAT
if cap_lane:
    SAT_EST = capped[cap_lane[0]][1] / (OLD_GREEN["J2"][1] / OLD_CYCLE["J2"])
print(f"estate saturation flow {SAT_EST:.0f}/h of green")
# the estate traffic the old plan held back is released east once J2 is retimed: it arrives at J3 and J4
released = 0 if (AB & {"pre", "ta"}) else sum(capped[k][0] - capped[k][1] for k in cap_lane if "offside" in chan[k]["lane"])
print(f"released estate traffic eastbound {released:.0f}/h")


# the bus gate cars also drove J1 -> J2 eastbound in the phase 2 week and will not any more. nothing
# else on that link changed with phase 2 (estate traffic joins after J2), so take it from the earlier
# term weeks, where nobody used the bus gate.
before = [d for d in term if d not in now]


def main_y(site, released_east=0.0):
    eb = [f + released_east / 2 for f in lane_flows(site, "A-road eastbound")]
    if site == "J2" and not (AB & {"nogate", "estonly", "pre", "mean", "ta"}):
        eb = [half_hour_peak(mean_curve(k, before)) for k in stop_lines("J2", "A-road eastbound")]
    return max(eb + lane_flows(site, "A-road westbound")) / SAT


ys = {
    "J1": [main_y("J1"), max(max(lane_flows("J1", "Mill Lane")), max(lane_flows("J1", "Fenwick Road"))) / SAT_SIDE],
    "J2": [main_y("J2"), max(est) / SAT_EST],
    "J3": [main_y("J3", released), max(lane_flows("J3", "School Lane")) / SAT_SIDE],
    "J4": [main_y("J4", released),
           max(max(lane_flows("J4", "Station Road")), max(lane_flows("J4", "Kiln Road"))) / SAT_SIDE],
}
print("flow ratios:", {j: [round(v, 3) for v in ys[j]] for j in ys})


# ---------------------------------------------------------------- design
def split(ys_, mins, usable):
    k = len(ys_)
    g = [0.0] * k
    free_ = list(range(k))
    rem = usable
    while True:
        tot = sum(ys_[i] for i in free_)
        fixed = [i for i in free_ if rem * ys_[i] / tot < mins[i]]
        if not fixed:
            break
        for i in fixed:
            g[i] = mins[i]
            rem -= mins[i]
            free_.remove(i)
    tot = sum(ys_[i] for i in free_)
    for i in free_:
        g[i] = rem * ys_[i] / tot
    gi = [int(round(x)) for x in g]
    diff = usable - sum(gi)
    order = sorted(range(k), key=lambda i: -ys_[i])
    j = 0
    while diff:
        i = order[j % k]
        st = 1 if diff > 0 else -1
        if gi[i] + st >= mins[i]:
            gi[i] += st
            diff -= st
        j += 1
    return gi


greens = {}
for j in ["J1", "J2", "J3"]:
    greens[j] = split(ys[j], MIN_G[j][:2], C - 3 * INTER - PED) + [PED]
g1 = greens["J3"][0] + J4_FOLLOW
greens["J4"] = [g1, C - 2 * INTER - g1]
for j, g in greens.items():
    assert sum(g) + len(g) * INTER == C, (j, g)
    assert all(a >= b for a, b in zip(g, MIN_G[j])), (j, g)
print("greens:", greens)

# ---------------------------------------------------------------- write, keeping the controller's phases
root = ET.parse(EXISTING).getroot()
out = ET.Element("additional")
for tl in root.iter("tlLogic"):
    j = tl.get("id")
    new = ET.SubElement(out, "tlLogic", {"id": j, "type": "static", "programID": "am_peak", "offset": str(OFFSETS[j])})
    stage = 0
    # the controller runs each stage green followed by its interstage (amber, all red, red + amber)
    for i, ph in enumerate(tl.iter("phase")):
        st = ph.get("state")
        dur = int(float(ph.get("duration")))
        if i % 4 == 0:
            dur = greens[j][stage]
            stage += 1
        ET.SubElement(new, "phase", {"duration": str(dur), "state": st})
    assert stage == len(greens[j]), (j, stage)
ET.indent(out)
ET.ElementTree(out).write(OUT, encoding="unicode")
print("wrote", OUT)
