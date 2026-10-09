"""Poll merge-render until terminal, reporting every 5 minutes."""
import datetime, sys, time
sys.path.insert(0, '/home/osboxes/Downloads/afterquery_kepler/kepler-tools')
import kepler_api as k

SID = "VMWZEk8EsZGOMdbvJe9r"
OUT = "/home/osboxes/Downloads/afterquery_kepler/kepler-tools/sp_watch.out"
STAGES = ["structure", "aiCheck", "similarity", "oracleNop", "qualityCheck",
          "cheatProbe", "trajectoryReview", "easinessProbe", "difficultyProbe",
          "runAudit"]


def say(m):
    line = "%s %s" % (datetime.datetime.now().strftime("%H:%M"), m)
    print(line, flush=True)
    open(OUT, "a").write(line + "\n")


last = None
deadline = time.time() + 12 * 3600
while time.time() < deadline:
    try:
        d = k.get(SID)
        p = d.get("pipeline") or {}
        st = d.get("status")
        bits = []
        for s in STAGES:
            v = p.get(s)
            if isinstance(v, dict):
                r = v.get("verdict") or v.get("status")
                if v.get("error"):
                    r = "ERR:" + str(v["error"])[:70]
                if r:
                    bits.append("%s=%s" % (s, r))
        cur = "%s | %s | %s" % (st, p.get("stage"), " ".join(bits))
        if cur != last:
            say(cur)
            last = cur
        if st in ("Needs Review", "Approved", "Rejected", "Validation Failed"):
            say("TERMINAL: %s" % st)
            sys.exit(0)
    except Exception as e:
        say("poll error: %s" % str(e)[:140])
    time.sleep(300)
say("deadline reached")
