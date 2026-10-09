#!/usr/bin/env python3
"""probe the vercel checkpoint every 5 minutes and submit hub-rollup the moment it lifts.

the token is re-read from token.txt on every call, so this survives token rotation as long as
the browser extension keeps pushing. writes a one line status to submit_watch.log each tick.
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "submit_watch.log"
ROOT = HERE.parent
ZIP = ROOT / "tasks/hub-rollup/hub-rollup.zip"
INTERVAL = 300
MAX_TICKS = 24                      # two hours

sys.path.insert(0, str(HERE))
import kepler_api as k              # noqa: E402


def log(msg):
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def probe():
    try:
        r = k._session().get("https://experts.afterquery.com/api/health",
                             headers=k._headers(json_body=False), timeout=25)
        return r.status_code
    except Exception as exc:                       # noqa: BLE001
        return "ERR %s" % type(exc).__name__


for tick in range(1, MAX_TICKS + 1):
    code = probe()
    if code == 429:
        log("tick %d/%d: still challenged (429)" % (tick, MAX_TICKS))
        if tick < MAX_TICKS:
            time.sleep(INTERVAL)
        continue
    log("tick %d: checkpoint cleared (HTTP %s), submitting" % (tick, code))
    r = subprocess.run([sys.executable, str(HERE / "kepler_api.py"), "submit", str(ZIP),
                        "hub-rollup", "Software", "Databases,Data engineering"],
                       capture_output=True, text=True, timeout=600)
    log("submit rc=%d" % r.returncode)
    log((r.stdout or "").strip()[-1500:])
    if r.returncode != 0:
        log("stderr: " + (r.stderr or "").strip()[-600:])
        if "429" in (r.stderr or "") and tick < MAX_TICKS:
            time.sleep(INTERVAL)
            continue
    sys.exit(0 if r.returncode == 0 else 1)

log("gave up after %d ticks, still challenged" % MAX_TICKS)
sys.exit(2)
