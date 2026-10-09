#!/usr/bin/env python3
"""Re-cut and resubmit a bundle until it clears validation.

    python3 kepler-tools/recut_loop.py <slug> <Category> <Label> <seed,seed,...> [prev_id]

Each round draws a fresh instance from the next seed, so the bytes genuinely
differ (the server 409s a byte-identical resubmission) and the bundle is a new
world rather than the same one re-sent. A similarity block costs a round and a
gap; any other verdict stops the loop with the reason.
"""
import json, os, subprocess, sys, time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
os.chdir(ROOT)
SLUG, CAT, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
SEEDS = [int(x) for x in sys.argv[4].split(",")]
prev = sys.argv[5] if len(sys.argv) > 5 else None
SRC = os.path.join("task-src", SLUG)
ZIP = os.path.join("tasks", SLUG, "%s.zip" % SLUG)
GAP = 1500          # seconds between a delete and the next send


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def api(*args, timeout=900):
    return run([sys.executable, "kepler-tools/kepler_api.py"] + list(args),
               timeout=timeout)


def log(msg):
    print("%s %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


for rnd, seed in enumerate(SEEDS, 1):
    log("round %d, seed %d" % (rnd, seed))
    r = run([sys.executable, "dev/gen.py", "write", str(seed)], cwd=SRC,
            timeout=3600)
    if r.returncode != 0:
        log("seed %d does not qualify, skipping: %s" % (seed, r.stderr[-200:]))
        continue
    o = run(["sg", "docker", "-c", "harbor run -p . -a oracle -e docker"],
            cwd=SRC, timeout=3600)
    if "1.000" not in o.stdout:
        log("oracle did not score 1 on seed %d, skipping" % seed)
        continue
    log("oracle 1.000")
    b = run([sys.executable, "kepler-tools/bundle.py", SRC, ZIP], timeout=600)
    if b.returncode != 0:
        log("bundle failed: %s" % b.stderr[-300:])
        continue

    if prev:
        log("deleting %s" % prev)
        api("delete", prev)
        prev = None
        log("gap of %ds" % GAP)
        time.sleep(GAP)

    s = api("submit", ZIP, SLUG, CAT, LABEL, timeout=1800)
    try:
        sid = json.loads(s.stdout[s.stdout.index("{"):])["submissionId"]
    except Exception:
        log("submit failed: %s" % (s.stdout[-300:] + s.stderr[-300:]))
        time.sleep(600)
        continue
    prev = sid
    log("submitted %s" % sid)

    verdict = None
    for _ in range(200):
        time.sleep(300)
        st = api("status", sid)
        try:
            d = json.loads(st.stdout)
        except Exception:
            continue
        p = d.get("pipeline") or {}
        log("%s stage=%s failed=%s" % (d.get("status"), p.get("stage"),
                                       p.get("failedStage")))
        if d.get("status") not in ("Validating", "Queued", "Pending"):
            verdict = (d.get("status"), p.get("failedStage"),
                       p.get("failureReason") or "")
            break
    if verdict is None:
        log("timed out watching %s" % sid)
        break
    log("VERDICT %s" % (verdict,))
    if verdict[1] is None:
        log("PASSED validation, stopping")
        break
    if verdict[1] != "similarity":
        log("stopped on a non-similarity verdict; needs a design change")
        break
log("loop finished")
