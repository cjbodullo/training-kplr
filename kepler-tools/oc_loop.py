import json, subprocess, sys, time

API = "/home/osboxes/Downloads/afterquery_kepler/kepler-tools/kepler_api.py"
LOG = "/home/osboxes/Downloads/afterquery_kepler/kepler-tools/oc_loop.txt"
ZIP = "/home/osboxes/Downloads/afterquery_kepler/tasks/offhire-clock/offhire-clock.zip"


def say(msg):
    line = "%s  %s" % (time.strftime("%H:%M:%S"), msg)
    open(LOG, "a").write(line + "\n")
    print(line, flush=True)


def api(*args, timeout=300):
    out = subprocess.run(["python3", API] + list(args), capture_output=True,
                         text=True, timeout=timeout)
    try:
        return json.loads(out.stdout)
    except Exception:
        return {"_raw": out.stdout[-500:], "_err": out.stderr[-500:]}


say("waiting 300s before resubmitting")
time.sleep(300)

res = api("submit", ZIP, "offhire-clock", "Software", "Data engineering,Algorithms")
sid = res.get("submissionId")
if not sid:
    say("SUBMIT FAILED: %s" % json.dumps(res)[:400])
    sys.exit(1)
say("submitted %s structureOk=%s" % (sid, res.get("structureOk")))

last = None
while True:
    time.sleep(300)
    d = api("status", sid, timeout=120)
    p = d.get("pipeline") or {}
    status = d.get("status")
    stages = {k: (v.get("verdict") or v.get("status"))
              for k, v in p.items() if isinstance(v, dict)}
    cur = json.dumps(stages)
    if cur != last:
        say("%s | %s | %s" % (status, p.get("stage"), cur))
        last = cur
    if status in ("Needs Review", "Approved", "Validation Failed", "Rejected"):
        say("TERMINAL %s" % status)
        for k, v in p.items():
            if isinstance(v, dict) and v.get("verdict") not in (None, "pass",
                                                                "passed"):
                say("%s -> %s" % (k, json.dumps(v)[:1200]))
        sys.exit(0)
