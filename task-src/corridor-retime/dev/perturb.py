import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evalplan
base = {"J1": {"greens": [59, 31, 9], "offset": 0}, "J2": {"greens": [51, 39, 9], "offset": 112},
        "J3": {"greens": [67, 23, 9], "offset": 0}, "J4": {"greens": [70, 36], "offset": 0}}
def mod(**kw):
    p = json.loads(json.dumps(base))
    for k, v in kw.items():
        j, what = k.split("_")
        if what == "off":
            p[j]["offset"] = (p[j]["offset"] + v) % 120
        else:
            i = int(what[1]); o = int(what[2])
            p[j]["greens"][i] += v; p[j]["greens"][o] -= v
    return p
variants = {
    "j2_est+3": mod(J2_g10=-3), "j2_est-3": mod(J2_g10=3), "j2_est-5": mod(J2_g10=5),
    "j3_sch+3": mod(J3_g10=-3), "j3_sch-3": mod(J3_g10=3),
    "j4_side+4": mod(J4_g10=-4), "j4_side-4": mod(J4_g10=4),
    "j2_off+8": mod(J2_off=8), "j2_off-8": mod(J2_off=-8), "j4_off+4": mod(J4_off=4), "j3j4_off+10": mod(J3_off=10, J4_off=10),
    "j1_side+4": mod(J1_g10=-4),
}
seeds = [int(x) for x in sys.argv[1].split(",")]
for name, p in variants.items():
    res = evalplan.evaluate(p, seeds, tag=name.replace("+", "p").replace("-", "m"))
    out = []
    for s, m in sorted(res.items()):
        bb = max(m["bb_seconds"].values()) if m["bb_seconds"] else 0
        out.append((int(m["depart_delay_max"]), bb))
    fails = sum(1 for dd, bb in out if dd > 120 or bb > 90)
    print(f"{name:12s} fail {fails}/{len(out)} {out}", flush=True)
