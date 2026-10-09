---
name: kepler-verifier
description: Step 5 of Kepler task authoring. Build the sealed tests/ verifier (test.sh writing reward.txt 0/1 + CTRF, separate Dockerfile, ground truth) plus a cheat/ attempt, hardened so grading needs real execution evidence.
---

# Kepler Verifier — SKILL

**pipeline position:** step 5 (build). prev → kepler-solution. next → kepler-validate.

build `tests/` — the sealed verifier that grades pass/fail — and a `cheat/` attempt that it must
reject. this is where the reward contract and anti-cheat rigor live. the agent never sees `tests/`.

## output
- `task-src/<slug>/tests/test.sh` (verifier entry point — writes the binary reward)
- `task-src/<slug>/tests/Dockerfile` (verifier image — bakes /tests, pre-installs tooling)
- `task-src/<slug>/tests/...` (test files + sealed ground truth)
- `task-src/<slug>/cheat/...` (a deliberate cheating attempt — never executed by harbor; you run it to confirm rejection)

---

## workflow

### step 1 — the reward contract (non-negotiable)
`test.sh` must write `/logs/verifier/reward.txt` containing exactly `0` or `1`, plus a CTRF test
report (pytest with the `pytest-json-ctrf` plugin). **every** code path — pass, fail, exception,
missing-file, timeout-adjacent — must still end by writing a reward. wrap grading so a crash yields
`0`, never a missing reward file. partial credit does not exist.

**the CTRF report must be at `/logs/verifier/ctrf.json`. that exact name.** the quality review has
a blocking `ctrf reporting` criterion and the harness tooling looks for `ctrf.json`; a report
written to `ctrf-report.json` is a validation failure even though the file is correct and complete
(edge-lower, 2026-09-12, failed on nothing else). older bundles in this repo use
`ctrf-report.json` — do not copy them. also guard the case where pytest dies before the plugin
runs, so the report exists on every path too:

```bash
python3 -m pytest /tests/test_x.py -p no:cacheprovider --ctrf "$LOGDIR/ctrf.json" -rA -vv \
    > "$LOGDIR/pytest.txt" 2>&1
rc=$?
cat "$LOGDIR/pytest.txt"
if [ ! -s "$LOGDIR/ctrf.json" ]; then
    python3 - <<'PY' || true
import json
json.dump({"results": {"tool": {"name": "pytest"},
                       "summary": {"tests": 0, "passed": 0, "failed": 1, "pending": 0,
                                   "skipped": 0, "other": 0, "start": 0, "stop": 0},
                       "tests": [{"name": "collection", "status": "failed", "duration": 0}]}},
          open("/logs/verifier/ctrf.json", "w"))
PY
fi
```

### step 2 — write the verifier Dockerfile
runs in its own container (`environment_mode = "separate"`) after the agent's container is torn
down. pre-install everything; `test.sh` must never apt-get / curl / pip install at verify time.

```dockerfile
FROM python:3.13-slim-bookworm

# pre-install everything the verifier needs — test.sh must never install at verify time
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install pytest==9.1.1 pytest-json-ctrf==0.5.2

# bake tests into the image — harbor does NOT upload tests/ at verify time
COPY . /tests/

# pre-create the parent dir of EVERY declared artifact, or harbor's upload fails
# with "Could not find the file /app in container"
RUN mkdir -p /app
```
pin every pip with `==`; apt unpinned + cleaned; add a `mkdir -p` line for each artifact parent dir.

### step 3 — write test.sh + the pytest tests
- `test.sh` runs pytest with the CTRF plugin, captures pass/fail, and writes `reward.txt`. example
  shape: run pytest → if all pass write `1` else `0`, and always write *something*.
- the tests read the agent's artifacts (declared in top-level `artifacts = [...]`) and compare
  against sealed ground truth baked into the image under `/tests/`.
- test the *outcome*, not the method — the agent may solve it differently from solve.sh.
- **grade the real format with the real reader.** if the artifact is a `.FCStd`, a parquet file, a
  protobuf message, an ELF binary, a coq `.vo`, a postgres dump — parse it with the actual library
  or tool, in the verifier image, and check real properties. a real parser rejects malformed output
  for free and is far harder to fake than a regex over text we invented. install that reader in
  `tests/Dockerfile` (pinned, pre-installed) like any other verifier tooling.

### step 4 — harden against cheating (this is graded by an adversarial probe)
- ground truth + grading logic live ONLY in `tests/`, never in the environment image.
- demand real execution evidence, not exit codes or agent-writable state. do not trust a file the
  agent could fabricate to say "I passed" — recompute / re-check the actual result.
- avoid checks an agent can satisfy by echoing the expected value; verify properties that only hold
  if the real work was done.
- **verifier execution isolation (this is a quality-check criterion — a task failed it).** if the
  agent produces *code* (a module/binary the verifier must run), do NOT import/exec it in the grader
  process — that lets agent code tamper with the reference, grading, or ground truth at import time.
  run the agent's code in a **subprocess** that only takes inputs and emits observations (e.g. JSON
  on stdout); keep the reference model + pass/fail decision in the trusted parent, which the agent
  process never shares. put the runner in its own dir and give it a neutral cwd so the grader's
  files (`model.py`, ground truth) are not on the agent's import path or reachable by relative open.
  reward.txt is set from pytest's exit code in the parent, so a forged reward from the subprocess
  is ignored. (see the mvcc task's `tests/runner/agent_runner.py` for the pattern.)

### step 5 — write and run the cheat/ attempt
put your best cheating attempt in `cheat/` (harbor never executes it — it's for you). try what the
anti-cheat probe will try: fabricate the artifact, hardcode the expected output, exploit a loose
check. then run your verifier against it and confirm it scores `0`. if it scores `1`, tighten the
verifier and repeat.

### step 6 — declare artifacts and timeouts
- top-level `artifacts = [...]` lists exact absolute paths the verifier reads from the agent
  (must be above the first `[section]` in task.toml).
- set `[verifier].timeout_sec` to cover the suite runtime (≤ 18000).

## checklist
- [ ] `test.sh` always writes `/logs/verifier/reward.txt` = exactly `0` or `1`, even on crash
- [ ] CTRF report produced via pytest + `pytest-json-ctrf`, written to `/logs/verifier/ctrf.json` (that exact name)
- [ ] verifier Dockerfile pre-installs all tooling, `COPY . /tests/`, `mkdir -p` each artifact parent
- [ ] pip pinned `==`, apt unpinned + cleaned
- [ ] ground truth only in tests/, never in environment
- [ ] grading requires real execution evidence, not agent-writable claims
- [ ] **artifact parsed with the real reader for its format where one exists (pinned in tests/Dockerfile)**
- [ ] cheat/ attempt written AND confirmed to score 0
- [ ] `artifacts = [...]` declared with exact absolute paths
