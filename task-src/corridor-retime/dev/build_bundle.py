"""write tests/sealed (net, controller spec, blocking back detectors, sealed days) and environment/data."""
import os, random, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, stages, demand, sumolib
import gen_history

ROOT = os.path.abspath(sys.argv[1])          # task-src/corridor-retime
HIST = os.path.abspath(sys.argv[2])          # dev/hist
SEEDS = [int(x) for x in sys.argv[3].split(",")]
sealed = os.path.join(ROOT, "tests", "sealed")
shutil.rmtree(sealed, ignore_errors=True)
os.makedirs(sealed)
netf = os.path.join(HIST, "_work", "net", "corridor.net.xml")
net = sumolib.net.readNet(netf)
shutil.copy(netf, os.path.join(sealed, "corridor.net.xml"))
shutil.copy(os.path.join(HIST, "_work", "old.add.xml"), os.path.join(sealed, "existing.add.xml"))
with open(os.path.join(sealed, "bb.add.xml"), "w") as f:
    f.write("<additional>\n")
    for eid in sim.INTERNAL:
        for ln in net.getEdge(eid).getLanes():
            f.write(f'    <laneAreaDetector id="bb_{ln.getID()}" lane="{ln.getID()}" pos="0.1" endPos="{ln.getLength() - 0.1:.2f}" '
                    f'period="1" file="bb.xml" timeThreshold="1.0" speedThreshold="1.4" jamThreshold="10.0"/>\n')
    f.write("</additional>\n")
for i, s in enumerate(SEEDS):
    vehs = demand.sample_day(random.Random(s), term=True, t1=10.5 * 3600, phase2=True)
    demand.write_routes(os.path.join(sealed, f"day{i + 1}.rou.xml"), net, vehs)
# agent environment
env = os.path.join(ROOT, "environment", "data")
shutil.rmtree(env, ignore_errors=True)
os.makedirs(os.path.join(env, "model"))
os.makedirs(os.path.join(env, "utc"))
shutil.copytree(os.path.join(ROOT, "dev", "docs_src"), os.path.join(env, "docs"))
shutil.copy(os.path.join(HIST, "docs", "orchard_way_bus_gate_BG1.csv"), os.path.join(env, "docs"))
shutil.copy(netf, os.path.join(env, "model", "corridor.net.xml"))
shutil.copy(os.path.join(HIST, "_work", "old.add.xml"), os.path.join(env, "model", "existing.add.xml"))
with open(os.path.join(env, "model", "car.vtype.xml"), "w") as f:
    f.write('<additional>\n    <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="4.6" minGap="2.5" maxSpeed="16.0" speedDev="0.1"/>\n</additional>\n')
for fn in os.listdir(os.path.join(HIST, "data")):
    shutil.copy(os.path.join(HIST, "data", fn), os.path.join(env, "utc", fn))
print("ok", os.listdir(sealed), os.listdir(env))
