import sys, json, importlib, types
RUN = sys.argv[1]
truth = json.load(open(f"{RUN}/truth.json"))
src = open("quorum.py").read()
V = {
 "reference": [],
 "no_term_rule": [("if lo == B == term_of[c + 1]:", "if False:")],
 "refused_is_unknown": [('elif "Connection refused" in r["error"]:', 'elif False:')],
 "no_realtime_rule": [('if any(t(w["ts"]) < t(z["sent"]) for z in committed_acked_in_P): continue', 'pass'),
                      ('if any(t(w["ts"]) < t(p["sent"]) for p in seq if p["status"] == "ok"): continue', 'pass'),
                      ('and not any(t(u["ts"]) < t(z["sent"]) for z in seq if z["status"] == "ok")', '')],
 "no_watch": [("if not check_watch(store.rev, written, None, store): return False", "pass")],
 "no_reads": [("if not check_read(store, q): return False", "pass")],
 "no_linearizability": [('if w["status"] != "ok" and not (w["rev_lo"] < r_w < w["rev_hi"]): continue', 'pass')],
 "no_quorum_cut": [('if w["after_quorum"]: continue', 'pass')],
 "dead_member_cutoff": [('w = {"sig": s, "sent": r["sent"], "ts": r["ts"], "svc": r["svc"]}',
                         'w = {"sig": s, "sent": r["sent"], "ts": r["ts"], "svc": r["svc"], "member": r["endpoint"].split("//")[1].split(":")[0]}'),
                        ('    for w in writes:\n        i = bisect.bisect_left(_done_t, _t(w["sent"]))',
                         '    _DEAD = {}\n    for r in calls:\n        if "error" in r and any(x in r["error"] for x in ("Connection refused", "Connection reset", "closed connection")):\n            m = r["endpoint"].split("//")[1].split(":")[0]; _DEAD[m] = min(_DEAD.get(m, 1e18), _t(r["ts"]))\n    for w in writes:\n        w["ts"] = w["ts"] if _t(w["ts"]) <= _DEAD.get(w["member"], 1e18) else _dt.utcfromtimestamp(_DEAD[w["member"]]).strftime("%Y-%m-%dT%H:%M:%S.%fZ")\n        i = bisect.bisect_left(_done_t, _t(w["sent"]))')],
 "hardstate_only": [("for c in range(C0, L + 1):", "for c in range(C0, C0 + 1):")],
}
ONLY = sys.argv[2:]
for name, subs in V.items():
    if ONLY and name not in ONLY: continue
    s = src
    for a, b in subs:
        assert a in s, (name, a); s = s.replace(a, b)
    m = types.ModuleType("q_" + name); exec(compile(s, name, "exec"), m.__dict__)
    try:
        A = m.analyze(f"{RUN}/members/m4/data", f"{RUN}/members/m5/data", f"{RUN}/logs")
        got = {k.decode(): v.decode() for k, v in A["present"].items()}
        unc = {k.decode() for k in A["uncertain"]}
        ok = got == truth["keys"] and unc == set(truth["uncertain"])
        print(f"{name:20s} pass={ok} keys {len(got)} (wrong {sum(1 for k in got if k in truth['keys'] and got[k]!=truth['keys'][k])}, extra {len(set(got)-set(truth['keys']))}, missing {len(set(truth['keys'])-set(got))}) uncertain {len(unc)} vs {len(truth['uncertain'])} worlds {len(A['worlds'])}")
    except Exception as e:
        print(f"{name:20s} pass=False ({type(e).__name__}: {str(e)[:80]})")
