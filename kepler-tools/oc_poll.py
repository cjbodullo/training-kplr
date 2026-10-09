import json, subprocess, sys, time
SID = "pptD6U3RJ3o4tJNkvWkN"
LOG = "/home/osboxes/Downloads/afterquery_kepler/kepler-tools/oc_poll.txt"
last = None
while True:
    try:
        d = json.loads(subprocess.run(
            ["python3", "/home/osboxes/Downloads/afterquery_kepler/kepler-tools/kepler_api.py",
             "status", SID], capture_output=True, text=True, timeout=120).stdout)
    except Exception as exc:
        time.sleep(300); continue
    p = d.get("pipeline") or {}
    status = d.get("status")
    stages = {k: (v.get("verdict") or v.get("status"))
              for k, v in p.items() if isinstance(v, dict)}
    line = "%s | %s | %s | %s" % (time.strftime("%H:%M:%S"), status,
                                  p.get("stage"), json.dumps(stages))
    if line.split("|", 1)[1] != (last or ""):
        open(LOG, "a").write(line + "\n")
        last = line.split("|", 1)[1]
    if status in ("Needs Review", "Approved", "Validation Failed", "Rejected"):
        open(LOG, "a").write("TERMINAL %s\n" % status)
        print("TERMINAL: %s" % status)
        print(json.dumps(stages, indent=1))
        for k, v in p.items():
            if isinstance(v, dict) and v.get("verdict") not in (None, "pass", "passed"):
                print(k, json.dumps(v)[:1500])
        sys.exit(0)
    time.sleep(300)
