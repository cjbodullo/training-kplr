"""run the old plan over the history weekdays in sumo and export the utc style loop data + survey."""
import csv, datetime, json, os, random, sys, shutil
import xml.etree.ElementTree as ET
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, stages, demand, sumolib

OUT = sys.argv[1]
WORK = os.path.join(OUT, "_work")
OLD_PLAN = {"J1": {"greens": [55, 25, 9], "offset": 0}, "J2": {"greens": [50, 30, 9], "offset": 31},
            "J3": {"greens": [61, 19, 9], "offset": 58}, "J4": {"greens": [70, 26], "offset": 62}}
PHASE2_FROM = datetime.date(2026, 11, 2)     # orchard way phase 2 occupied
DAYS = [datetime.date(2026, 10, 12) + datetime.timedelta(days=i) for i in range(26)]
DAYS = [d for d in DAYS if d.weekday() < 5]
HALF_TERM = {datetime.date(2026, 10, 26) + datetime.timedelta(days=i) for i in range(5)}
SURVEY_DAY = datetime.date(2026, 10, 28)
T_BEGIN, T_DEMAND_END, T_END = 6.75 * 3600, 12.0 * 3600, 12.0 * 3600
REPORT_FROM = 7 * 3600

# utc channel numbering per site: (lane id, position kind)
def channel_plan(net):
    plan = []
    for site, apps in [("J1", ["a_w_in", "a_21", "j1n_in", "j1s_in"]), ("J2", ["a_12", "a_32", "j2s_in"]),
                       ("J3", ["a_23", "a_43", "j3n_in"]), ("J4", ["a_34", "a_e_in", "j4n_in", "j4s_in"])]:
        k = 0
        for a in apps:
            for ln in net.getEdge(a).getLanes():
                k += 1
                plan.append((site, f"D{k}", ln.getID(), "sl"))
            if a in sim.ENTRY:
                for ln in net.getEdge(a).getLanes():
                    k += 1
                    plan.append((site, f"D{k}", ln.getID(), "up"))
    return plan


P_DIVERT = 0.45          # share of eastbound estate drivers who cut through the bus gate while the queue stands
QUEUE_OCC = 50.0         # estate offside upstream loop occupancy (%) that means the queue is over it
BUS_GATE_S = 60.0        # estate departure -> bus gate camera
FENWICK_S = 120.0        # estate departure -> Fenwick Road (j1s_in) entry


def queued_bins(wd):
    """5 min bins where the estate offside lane queue stood over its upstream loop."""
    out = set()
    for iv in ET.parse(os.path.join(wd, "loops.xml")).getroot():
        if iv.get("id") == "up_j2s_in_1" and float(iv.get("occupancy")) > QUEUE_OCC:
            out.add(int(float(iv.get("begin")) // 300))
    return out


def run(args):
    i, d = args
    netf = os.path.join(WORK, "net", "corridor.net.xml")
    net = sumolib.net.readNet(netf)
    term = d not in HALF_TERM
    vehs = demand.sample_day(random.Random(1000 + i), term=term, t1=T_DEMAND_END, phase2=d >= PHASE2_FROM)
    rf = os.path.join(WORK, f"{d}.rou.xml")
    wd = os.path.join(WORK, str(d))
    extra = (["--vehroute-output", os.path.join(wd, "vehroutes.xml"), "--vehroute-output.exit-times", "true"]
             if d == SURVEY_DAY else [])
    demand.write_routes(rf, net, vehs)
    sim.run_day(netf, rf, [os.path.join(WORK, "old.add.xml")], os.path.join(WORK, "det.add.xml"), wd,
                begin=T_BEGIN, end=T_END, seed=1000 + i, extra=extra)
    gate = []
    if d >= PHASE2_FROM:
        # second pass: while the estate queue stands, some eastbound estate drivers rat run through the
        # bus gate and join the corridor on Fenwick Road at J1 instead of turning right at J2
        q = queued_bins(wd)
        rng = random.Random(5000 + i)
        new = []
        for t, a, b in vehs:
            if a == "j2s_in" and b in ("a_e_out", "j4n_out") and int(t // 300) in q and rng.random() < P_DIVERT:
                new.append((t + FENWICK_S, "j1s_in", b))
                gate.append(t + BUS_GATE_S)
            else:
                new.append((t, a, b))
        new.sort()
        demand.write_routes(rf, net, new)
        sim.run_day(netf, rf, [os.path.join(WORK, "old.add.xml")], os.path.join(WORK, "det.add.xml"), wd,
                    begin=T_BEGIN, end=T_END, seed=1000 + i, extra=extra)
        # camera also catches the odd driver at other times (deliveries, people who ignore the signs)
        for _ in range(rng.randint(2, 6)):
            gate.append(rng.uniform(7 * 3600, 12 * 3600))
    with open(os.path.join(WORK, f"{d}.gate.json"), "w") as f:
        json.dump(sorted(gate), f)
    return str(d), len(vehs), len(gate)



ARM_NAME = {"a_w_in": "west", "a_w_out": "west", "a_e_in": "east", "a_e_out": "east", "a_12": "east", "a_21": "east",
            "a_23": "east", "a_32": "east", "a_34": "east", "a_43": "east"}
DESC = {  # approach edge -> (arm text, lane texts)
    "a_w_in": ("A-road eastbound", ["nearside (left + ahead)", "offside (ahead)"]),
    "a_21": ("A-road westbound", ["nearside (left + ahead)", "offside (ahead)"]),
    "j1n_in": ("Mill Lane southbound", ["single lane"]),
    "j1s_in": ("Fenwick Road northbound", ["single lane"]),
    "a_12": ("A-road eastbound", ["nearside (ahead)", "offside (ahead)"]),
    "a_32": ("A-road westbound", ["nearside (left + ahead)", "offside (ahead)"]),
    "j2s_in": ("Orchard Way northbound (estate)", ["nearside (left)", "offside (right)"]),
    "a_23": ("A-road eastbound", ["nearside (left + ahead)", "offside (ahead)"]),
    "a_43": ("A-road westbound", ["nearside (ahead)", "offside (ahead)"]),
    "j3n_in": ("School Lane southbound", ["single lane (left + right)"]),
    "a_34": ("A-road eastbound", ["nearside (left + ahead)", "offside (ahead)"]),
    "a_e_in": ("A-road westbound", ["nearside (left + ahead)", "offside (ahead)"]),
    "j4n_in": ("Station Road southbound", ["single lane"]),
    "j4s_in": ("Kiln Road northbound", ["single lane"]),
}
# faults, keyed by (site, lane id, kind)
DOUBLE = ("J2", "a_32_0", "sl")                       # chattering loop, counts every vehicle twice
SWAP = (("J3", "j3n_in_0", "sl"), ("J3", "a_43_0", "sl"))   # feeders crossed at the cabinet
STUCK = (("J4", "j4s_in_0", "sl"), datetime.date(2026, 10, 21))   # stuck on from this date


def export(net, days):
    chans = channel_plan(net)
    lane_len = {ln.getID(): ln.getLength() for e in net.getEdges() for ln in e.getLanes()}
    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "docs"), exist_ok=True)
    with open(os.path.join(OUT, "data", "channels.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["site", "channel", "approach", "lane", "loop", "distance_to_stop_line_m", "sumo_lane"])
        for site, ch, lane, kind in chans:
            edge, idx = lane.rsplit("_", 1)
            arm, lanes = DESC[edge]
            dist = 2.0 if kind == "sl" else min(160.0, lane_len[lane] - 5.0)
            w.writerow([site, ch, arm, lanes[int(idx)], "stop line" if kind == "sl" else "upstream",
                        f"{dist:.0f}", lane])
    key_of = {(site, lane, kind): ch for site, ch, lane, kind in chans}
    src_of = {k: k for k in key_of}
    src_of[SWAP[0]], src_of[SWAP[1]] = SWAP[1], SWAP[0]
    rows = []
    for d in days:
        data = {}
        for iv in ET.parse(os.path.join(WORK, str(d), "loops.xml")).getroot():
            t = float(iv.get("begin"))
            if t < REPORT_FROM or t >= T_END:
                continue
            kind, lane = iv.get("id").split("_", 1)
            data[(kind, lane, t)] = (int(iv.get("nVehContrib")), float(iv.get("occupancy")))
        for site, ch, lane, kind in chans:
            s_site, s_lane, s_kind = src_of[(site, lane, kind)]
            for t in sorted({k[2] for k in data}):
                n, occ = data[(s_kind, s_lane, t)]
                if (site, lane, kind) == DOUBLE:
                    n = 2 * n
                if (site, lane, kind) == STUCK[0] and d >= STUCK[1]:
                    n, occ = 0, 100.0
                hh, mm = int(t // 3600), int(t % 3600 // 60)
                rows.append([d.isoformat(), site, ch, f"{hh:02d}:{mm:02d}", n, f"{occ:.1f}"])
    with open(os.path.join(OUT, "data", "utc_counts.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "site", "channel", "period_start", "count", "occupancy_pct"])
        w.writerows(rows)
    # bus gate camera log (warning notices, camera live from the phase 2 week)
    rng = random.Random(77)
    letters = "ABCDEFGHJKLMNPRSTUVWXY"
    with open(os.path.join(OUT, "docs", "orchard_way_bus_gate_BG1.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "time", "camera", "vrm", "vehicle_class", "outcome"])
        for d in days:
            if d < PHASE2_FROM:
                continue
            for t in json.load(open(os.path.join(WORK, f"{d}.gate.json"))):
                vrm = rng.choice(letters) + rng.choice(letters) + f"{rng.randint(10, 74):02d} " + rng.choice(letters) + "**"
                hh, mm, ss = int(t // 3600), int(t % 3600 // 60), int(t % 60)
                w.writerow([d.isoformat(), f"{hh:02d}:{mm:02d}:{ss:02d}", "BG1 Orchard Way bus gate", vrm, "car",
                            "warning notice"])
    # manual classified turning count at J3 on the survey day, 07:30-09:30, 15 min
    arm = {"a_23": "A-road west arm", "a_43": "A-road east arm", "j3n_in": "School Lane",
           "a_34": "A-road east arm", "a_32": "A-road west arm", "j3n_out": "School Lane"}
    cnt = {}
    for v in ET.parse(os.path.join(WORK, str(SURVEY_DAY), "vehroutes.xml")).getroot().iter("vehicle"):
        r = v.find("route")
        edges = r.get("edges").split()
        ex = [float(x) for x in r.get("exitTimes").split()]
        for i in range(len(edges) - 1):
            if edges[i] in ("a_23", "a_43", "j3n_in"):
                t = ex[i]
                if 7.5 * 3600 <= t < 9.5 * 3600:
                    b = int(t // 900) * 900
                    k = (b, arm[edges[i]], arm[edges[i + 1]])
                    cnt[k] = cnt.get(k, 0) + 1
    moves = sorted({(k[1], k[2]) for k in cnt})
    with open(os.path.join(OUT, "data", f"mcc_J3_{SURVEY_DAY.isoformat()}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["period_start", "from_arm", "to_arm", "cars"])
        for b in range(int(7.5 * 3600), int(9.5 * 3600), 900):
            for fa, ta in moves:
                w.writerow([f"{b // 3600:02d}:{b % 3600 // 60:02d}", fa, ta, cnt.get((b, fa, ta), 0)])


if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    netf = sim.build_net(os.path.join(WORK, "net"))
    net = sumolib.net.readNet(netf)
    stages.write_tls(os.path.join(WORK, "old.add.xml"), net, OLD_PLAN, program_id="existing")
    sim.write_detectors(os.path.join(WORK, "det.add.xml"), net, loop_period=300)
    if "--export-only" not in sys.argv:
        with Pool(int(os.environ.get("PROCS", "7"))) as p:
            res = p.map(run, list(enumerate(DAYS)))
        print(res)
    export(net, DAYS)
