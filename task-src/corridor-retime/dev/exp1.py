import json, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, stages, demand
import sumolib

out = sys.argv[1]
plan = json.loads(sys.argv[2])
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
term = (sys.argv[4] != "half") if len(sys.argv) > 4 else True
netf = sim.build_net(os.path.join(out, "net"))
net = sumolib.net.readNet(netf)
for t in ["J1", "J2", "J3", "J4"]:
    mv = stages.link_movements(net, t)
    if seed == 1:
        print(t, {i: mv[i] for i in sorted(mv)})
stages.write_tls(os.path.join(out, "plan.add.xml"), net, plan)
sim.write_detectors(os.path.join(out, "det.add.xml"), net)
rng = random.Random(seed)
vehs = demand.sample_day(rng, term=term)
demand.write_routes(os.path.join(out, "day.rou.xml"), net, vehs)
t0 = time.time()
sim.run_day(netf, os.path.join(out, "day.rou.xml"), [os.path.join(out, "plan.add.xml")],
            os.path.join(out, "det.add.xml"), os.path.join(out, "run"), seed=seed)
m = sim.metrics(os.path.join(out, "run"), len(vehs))
print("sim s", round(time.time() - t0, 1))
print({k: v for k, v in m.items() if k != "waits"})
for a, w in sorted(m["waits"].items()):
    print(f"  {a:10s} p95 {w[0]:6.1f} max {w[1]:6.1f} mean {w[2]:6.1f}")
