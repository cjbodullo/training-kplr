"""Wait until similarity is observed clearing for anybody AFTER my block."""
import json, subprocess, sys, time

SID = "SqvB5VfqeUx6FEaaqM7S"


def listing():
    out = subprocess.check_output(
        [sys.executable, "kepler-tools/kepler_api.py", "list"], text=True, timeout=240)
    return json.loads(out)


mine = None
for t in listing():
    if t["id"] == SID:
        mine = ((t.get("pipeline") or {}).get("similarity") or {}).get("ranAt")
print("my block ran at", time.strftime("%H:%M:%S", time.localtime(mine / 1000)),
      "epoch", mine, flush=True)

deadline = time.time() + 8 * 3600
seen = set()
while time.time() < deadline:
    try:
        rows = []
        for t in listing():
            if t.get("deletedAt"):
                continue
            sim = ((t.get("pipeline") or {}).get("similarity") or {})
            if sim.get("ranAt", 0) > mine:
                rows.append((sim["ranAt"], t["taskName"], sim.get("status")))
        rows.sort()
        for r in rows:
            if r not in seen:
                seen.add(r)
                print(time.strftime("%H:%M:%S"), "->",
                      time.strftime("%H:%M", time.localtime(r[0] / 1000)),
                      r[1], r[2], flush=True)
        passed = [r for r in rows if r[2] == "passed"]
        if passed:
            print("CLEAR", passed[-1][1], "passed similarity after my block", flush=True)
            break
    except Exception as exc:
        print(time.strftime("%H:%M:%S"), "poll error:", exc, flush=True)
    time.sleep(600)
else:
    print("TIMEOUT with no similarity pass observed", flush=True)
