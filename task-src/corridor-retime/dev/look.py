import csv, collections, sys, xml.etree.ElementTree as ET, glob, os
D = sys.argv[1]
rows = list(csv.DictReader(open(f"{D}/data/utc_counts.csv")))
ch = {(r["site"], r["channel"]): r for r in csv.DictReader(open(f"{D}/data/channels.csv"))}
day = sys.argv[2]
agg = collections.defaultdict(lambda: collections.Counter())
occ = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    if r["date"] != day: continue
    k = (r["site"], r["channel"])
    h = r["period_start"][:2] + ":" + ("00" if int(r["period_start"][3:]) < 30 else "30")
    agg[k][h] += int(r["count"]); occ[k][h].append(float(r["occupancy_pct"]))
for k in sorted(agg, key=lambda k: (k[0], int(k[1][1:]))):
    c = ch[k]
    print(k, c["approach"][:22], c["lane"][:14], c["loop"][:4], " ".join(f"{agg[k][h]*2:4d}/{sum(occ[k][h])/len(occ[k][h]):3.0f}" for h in sorted(agg[k])))
for d in sorted(glob.glob(f"{D}/_work/2026-*/stats.xml")):
    st = ET.parse(d).getroot()
    print(os.path.basename(os.path.dirname(d)), "tele", st.find("teleports").get("total"), "waiting", st.find("vehicles").get("waiting"), "ins", st.find("vehicles").get("inserted"), "loaded", st.find("vehicles").get("loaded"))
