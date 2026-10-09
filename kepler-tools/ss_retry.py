"""One conservative retry of the held sign-schedule zip, after the index turns over.

Waits out the ghost chain, then requires a control: some OTHER bundle must have
cleared similarity recently, so a block means my content and not the gate.
Submits exactly once and stops either way.
"""
import json, subprocess, sys, time

ZIP = "tasks/sign-schedule/sign-schedule.zip"
WAIT = 5 * 3600


def api(*args, timeout=300):
    return json.loads(subprocess.check_output(
        [sys.executable, "kepler-tools/kepler_api.py", *args], text=True, timeout=timeout))


print("holding the zip until", time.strftime("%H:%M", time.localtime(time.time() + WAIT)), flush=True)
time.sleep(WAIT)

for attempt in range(6):
    try:
        rows = []
        for t in api("list"):
            if t.get("deletedAt"):
                continue
            sim = ((t.get("pipeline") or {}).get("similarity") or {})
            if sim.get("ranAt"):
                rows.append((sim["ranAt"], t["taskName"], sim.get("status")))
        rows.sort(reverse=True)
        recent = [r for r in rows if r[0] > (time.time() - 5400) * 1000]
        control = [r for r in recent if r[2] == "passed" and r[1] != "sign-schedule"]
        print(time.strftime("%H:%M:%S"), "recent similarity runs:",
              [(r[1], r[2]) for r in recent], flush=True)
        if not recent:
            print("  no recent runs to judge the gate by, waiting", flush=True)
        elif not control:
            print("  no other bundle has cleared recently, waiting", flush=True)
        else:
            for t in api("list"):
                if t["taskName"] == "sign-schedule" and not t.get("deletedAt"):
                    api("delete", t["id"])
                    print("  deleted stale record", t["id"], flush=True)
            out = api("submit", ZIP, "sign-schedule", "Media", "Design", timeout=600)
            print("SUBMITTED", json.dumps(out), flush=True)
            break
    except Exception as exc:
        print(time.strftime("%H:%M:%S"), "retry error:", exc, flush=True)
    time.sleep(1800)
else:
    print("gave up waiting for a control pass", flush=True)
