import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, stages, demand, sumolib
import xml.etree.ElementTree as ET
out = sys.argv[1]; dest = sys.argv[2]
netf = sim.build_net(os.path.join(out, "net")); net = sumolib.net.readNet(netf)
plan = {"J1": {"greens": [60, 7, 9], "offset": 0}, "J2": {"greens": [83, 7], "offset": 0},
        "J3": {"greens": [76, 5, 7], "offset": 0}, "J4": {"greens": [76, 7, 9], "offset": 0}}
# cycle check
print({k: stages.cycle_of(v["greens"]) for k, v in plan.items()})
stages.write_tls(os.path.join(out, "plan.add.xml"), net, plan)
sim.write_detectors(os.path.join(out, "det.add.xml"), net, loop_period=120)
rng = random.Random(3)
vehs = []
t = 6.75 * 3600
while t < 7.5 * 3600:
    t += rng.expovariate(3000 / 3600)
    vehs.append((t, "a_w_in", dest))
demand.write_routes(os.path.join(out, "d.rou.xml"), net, vehs)
sim.run_day(netf, os.path.join(out, "d.rou.xml"), [os.path.join(out, "plan.add.xml")], os.path.join(out, "det.add.xml"),
            os.path.join(out, "run"), end=7.6 * 3600)
tot = {}
for iv in ET.parse(os.path.join(out, "run", "loops.xml")).getroot():
    if iv.get("id").startswith("sl_a_w_in"):
        tot.setdefault(iv.get("id"), []).append(int(iv.get("nVehContrib")))
for k, v in tot.items():
    print(k, v[3:20])
