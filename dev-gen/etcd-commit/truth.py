"""sealed ground truth for the tarn-kv outage: evidence only analysis (quorum.py) plus a check that the real
history (m2's log, never shipped) is consistent with every value the analysis calls determined.

usage: truth.py RUNDIR OUT.json [v]
"""
import sys, json
from walparse import dump
from mvcc import Store
from quorum import analyze, sig_entry, ABSENT

RUN, OUT = sys.argv[1], sys.argv[2]
A = analyze(f"{RUN}/members/m4/data", f"{RUN}/members/m5/data", f"{RUN}/logs")
present, determined, uncertain, worlds = A["present"], A["determined"], A["uncertain"], A["worlds"]
acked, writes, P, L = A["acked"], A["writes"], A["P"], A["L"]
# ---------- real history: m2's log through the last acked or committed entry
hs2, P2 = dump(f"{RUN}/members/m2/data")
true_end = max([hs2["commit"]] + [e["index"] for e in P2 if e["req"] and sig_entry(e["req"]) in acked])
real = Store()
for e in P2:
    if e["index"] > true_end: break
    if e["req"]: real.apply(e["req"])
for k, v in present.items():
    assert k in real.kv and real.kv[k]["value"] == v, ("determined key differs from the real history", k)
for k, v in determined.items():
    if v is ABSENT: assert k not in real.kv, ("determined absent key exists", k)
real_seq_ok = any(c == min(L, true_end) for c, *_ in worlds)

stats = {"C0": A["C0"], "L": L, "divergence": A["D"], "m5_last": A["E5"][-1]["index"], "rev_C0": A["rev_C0"], "maxR": A["maxR"],
         "worlds": len(worlds), "c_values": sorted({w[0] for w in worlds}), "S0_len": [len(w[1]) for w in worlds][:5],
         "free": [len(w[3]) for w in worlds][:5], "max_component": A["max_comp"], "present": len(present),
         "uncertain": len(uncertain), "absent_determined": sum(1 for v in determined.values() if v is ABSENT),
         "real_c_in_worlds": real_seq_ok, "term_pruned": A["term_pruned"],
         "gapfills": sum(1 for c, seq, *_ in worlds for sg in seq if sg not in acked),
         "L_acked": any(sig_entry(e["req"]) in acked for e in P if e["index"] == L and e["req"]), "true_end": true_end,
         "acked_unseen": len([w for w in writes if w["status"] == "ok" and w["sig"] not in A["ent_of"]])}
print(json.dumps(stats, indent=1))
json.dump({"keys": {k.decode(): v.decode() for k, v in sorted(present.items())},
           "uncertain": [k.decode() for k in uncertain], "stats": stats}, open(OUT, "w"), indent=1)
if len(sys.argv) > 3:
    for c, seq, s_end, free in worlds:
        bysig = {w["sig"]: w for w in writes}
        gaps = [(i + 1, bysig[sg]["svc"], sg[0], bysig[sg]["status"], bysig[sg]["ts"][17:]) for i, sg in enumerate(seq) if bysig[sg]["status"] != "ok"]
        print("world c=%d rev_c=%d S0=%d gapfill=%s free=%d" % (c, s_end.rev - len(seq), len(seq), gaps, len(free)))
    print("P tail:", [(e["index"], e["term"], (sig_entry(e["req"]) or ("-",))[0], acked.get(sig_entry(e["req"]), {}).get("rev") if e["req"] else None) for e in P if e["index"] > A["C0"] - 2])
    print("uncertain:", [k.decode() for k in uncertain])
    unk = [w for w in writes if w["status"] == "unknown"]
    import collections
    print("unknown calls:", len(unk), collections.Counter(("inP" if w["sig"] in A["ent_of"] else "dead" if w["sig"] in A["dead_sigs"] else "other") for w in unk))
