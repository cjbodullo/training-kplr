import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evalplan
base = {"J1": {"greens": [59, 31, 9], "offset": 0}, "J2": {"greens": [51, 39, 9], "offset": 112},
        "J3": {"greens": [67, 23, 9], "offset": 0}, "J4": {"greens": [70, 36], "offset": 0}}
j = sys.argv[1]; vals = [int(x) for x in sys.argv[2].split(",")]; seeds = [int(x) for x in sys.argv[3].split(",")]
tot = sum(base[j]["greens"][:2])
for v in vals:
    p = json.loads(json.dumps(base))
    p[j]["greens"][1] = v; p[j]["greens"][0] = tot - v
    if j == "J3":
        p["J4"]["greens"] = [p["J3"]["greens"][0] + 3, 106 - p["J3"]["greens"][0] - 3]
    res = evalplan.evaluate(p, seeds, tag=f"sw{j}{v}")
    out = [(int(m["depart_delay_max"]), max(m["bb_seconds"].values()) if m["bb_seconds"] else 0) for s, m in sorted(res.items())]
    fails = sum(1 for dd, bb in out if dd > 120 or bb > 90)
    print(f"{j} side {v}: fail {fails}/{len(out)} dd {sorted(x[0] for x in out)[-4:]} bb {sorted(x[1] for x in out)[-3:]}", flush=True)
