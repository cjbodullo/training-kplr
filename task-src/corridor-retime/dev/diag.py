import json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demand, design, evalplan, sumolib, offdesc
import xml.etree.ElementTree as ET
evalplan.prep()
net = sumolib.net.readNet(os.path.join(evalplan.BASE, "corridor.net.xml"))
C = int(sys.argv[1]); seed = int(sys.argv[2])
plan = json.loads(sys.argv[3]) if len(sys.argv) > 3 else design.design(offdesc.true_movs(net), C, {})
res = evalplan.evaluate(plan, [seed], tag="diag")
wd = os.path.join(evalplan.BASE, "runs", f"diag_{seed}")
# bb timeline in 5 min bins
tl = collections.defaultdict(lambda: collections.Counter())
for iv in ET.parse(os.path.join(wd, "bb.xml")).getroot():
    if float(iv.get("maxJamLengthInMeters", "0")) > 0:
        tl[iv.get("id")][int(float(iv.get("begin")) // 900) * 15] += 1
for k, v in sorted(tl.items()):
    print(k, {f"{m//60:02d}:{m%60:02d}": c for m, c in sorted(v.items())})
# stop line flows on J3/J4 approaches per 15 min
fl = collections.defaultdict(lambda: collections.Counter())
occ = collections.defaultdict(lambda: collections.Counter())
for iv in ET.parse(os.path.join(wd, "loops.xml")).getroot():
    i = iv.get("id")
    if i.startswith("sl_a_23") or i.startswith("sl_a_34") or i.startswith("sl_a_43") or i.startswith("up_") and "a_e_in" in i:
        b = int(float(iv.get("begin")) // 900) * 15
        fl[i][b] += int(iv.get("nVehContrib"))
for k, v in sorted(fl.items()):
    print(k, [v[m] * 4 for m in sorted(v)][:16])
