"""evaluate a plan on n sampled days (parallel)."""
import json, os, random, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, stages, demand, sumolib

BASE = "/tmp/evalnet"


def prep():
    netf = os.path.join(BASE, "corridor.net.xml")
    if os.path.exists(netf) and not sim.LANE_LEN:
        sim.load_lengths(netf)
    if not os.path.exists(netf):
        sim.build_net(BASE)
        net = sumolib.net.readNet(netf)
        sim.write_detectors(os.path.join(BASE, "det.add.xml"), net)
    return netf


def day_routes(seed, term=True):
    p = os.path.join(BASE, f"day_{'t' if term else 'h'}{os.environ.get('P2', '0')}_{seed}.rou.xml")
    if not os.path.exists(p):
        net = sumolib.net.readNet(os.path.join(BASE, "corridor.net.xml"))
        vehs = demand.sample_day(random.Random(seed), term=term, t1=10.5 * 3600, phase2=os.environ.get("P2") == "1")
        demand.write_routes(p, net, vehs)
        open(p + ".n", "w").write(str(len(vehs)))
    return p, int(open(p + ".n").read())


def one(args):
    tag, plan_file, seed, term = args
    netf = os.path.join(BASE, "corridor.net.xml")
    if not sim.LANE_LEN:
        sim.load_lengths(netf)
    r, n = day_routes(seed, term)
    wd = os.path.join(BASE, "runs", f"{tag}_{seed}")
    sim.run_day(netf, r, [plan_file], os.path.join(BASE, "det.add.xml"), wd, seed=1, end=11.0 * 3600)
    m = sim.metrics(wd, n)
    return seed, m


def evaluate(plan, seeds, tag="p", term=True, procs=7):
    netf = prep()
    net = sumolib.net.readNet(netf)
    pf = os.path.join(BASE, f"plan_{tag}.add.xml")
    stages.write_tls(pf, net, plan)
    for s in seeds:
        day_routes(s, term)
    with Pool(procs) as p:
        res = p.map(one, [(tag, pf, s, term) for s in seeds])
    return dict(res)


def summarize(res):
    lines = []
    for s, m in sorted(res.items()):
        bb = sum(m["bb_seconds"].values())
        worst = max(m["waits"].items(), key=lambda kv: kv[1][0])
        lines.append(f"seed {s}: tele {m['teleports']} arr {m['arrived']}/{m['n']} ddmax {m['depart_delay_max']:.0f} "
                     f"bb {bb} {dict(m['bb_seconds'])} worst p95 {worst[0]} {worst[1][0]:.0f}")
    return "\n".join(lines)


if __name__ == "__main__":
    plan = json.loads(sys.argv[1])
    seeds = [int(x) for x in sys.argv[2].split(",")]
    print(summarize(evaluate(plan, seeds)))
