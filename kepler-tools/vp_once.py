#!/usr/bin/env python3
"""One submission of volume-post after a long gap, then the normal gates.

Four submit-and-delete cycles of this zip inside ninety minutes left ghosts of
it in the similarity index, and each retry matched its own predecessor.  So:
wait for them to age out, submit ONCE, and do not delete-and-retry on a
similarity block -- if it blocks again with the gate demonstrably passing other
tasks, that is a content verdict and it needs a content answer, not another
round.
"""
import subprocess
import sys
import time

ROOT = "/home/osboxes/Downloads/afterquery_kepler"
GAP = 3 * 3600

print("holding %d seconds before a single submission" % GAP, flush=True)
time.sleep(GAP)
print("%s submitting volume-post, one shot" % time.strftime("%H:%M:%S"), flush=True)
subprocess.run(
    [sys.executable, "-u", "kepler-tools/kepler_run.py", "loop",
     "--zip", "tasks/volume-post/volume-post.zip",
     "--name", "volume-post", "--category", "ML",
     "--labels", "Data engineering",
     "--src", "task-src/volume-post",
     "--similarity-retries", "0", "--max-rounds", "1", "--interval", "20"],
    cwd=ROOT)
