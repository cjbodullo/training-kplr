#!/usr/bin/env python3
"""Submit as soon as a validation slot frees, then hand off to loop_attach.py.

The account allows ten tasks validating at once. When every slot is taken the
submit call comes back TOO_MANY_REQUESTS; this waits for a slot rather than
deleting somebody else's in flight task, then runs the normal watch / infra
resubmit / save-the-feedback loop on the new submission.

    python3 kepler-tools/submit_when_free.py --zip Z --name N --category C \
        --labels a,b --src DIR [--interval 180]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kepler_api as api

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--src", default=None)
    ap.add_argument("--interval", type=int, default=180)
    args = ap.parse_args()

    waited = 0
    while True:
        try:
            fin = api.submit(args.zip, args.name, args.category, args.labels.split(","))
            sid = fin.get("submissionId")
            print("submissionId: %s | structureOk: %s" % (sid, fin.get("structureOk")), flush=True)
            for f in fin.get("findings", []):
                print("  finding [%s] %s: %s" % (f.get("level"), f.get("code"), f.get("message")),
                      flush=True)
            if not sid:
                return 2
            break
        except Exception as e:
            msg = str(e)
            if "TOO_MANY_REQUESTS" in msg or "being validated" in msg:
                waited += args.interval
                print("all ten validation slots busy, waited %ds, retrying" % waited, flush=True)
                time.sleep(args.interval)
                continue
            print("submit failed: %s" % msg[:300], flush=True)
            time.sleep(args.interval)

    cmd = [sys.executable, "-u", str(HERE / "loop_attach.py"), sid,
           "--zip", args.zip, "--name", args.name, "--category", args.category,
           "--labels", args.labels]
    if args.src:
        cmd += ["--src", args.src]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
