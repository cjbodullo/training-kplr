---
name: kepler-solution
description: Step 4 of Kepler task authoring. Write solution/solve.sh (and helpers), the deterministic reference solution that must score exactly 1 on the oracle run every time.
---

# Kepler Solution — SKILL

**pipeline position:** step 4 (build). prev → kepler-environment. next → kepler-verifier.

write `solution/solve.sh` — the reference solution. it runs against the untouched environment and
must score **exactly 1**, every time. this is both the proof the task is solvable and the ground
truth the verifier is designed around.

## output
- `task-src/<slug>/solution/solve.sh` (required, must score 1)
- `task-src/<slug>/solution/...` (optional helpers called by solve.sh)

---

## workflow

### step 1 — understand the mount contract
`solution/` is mounted **only** for the oracle run. `solve.sh` executes inside the agent's
environment container. it should produce exactly the artifacts the instruction promises, at the
absolute paths the instruction and `artifacts = [...]` declare.

### step 2 — write solve.sh
- start with `#!/usr/bin/env bash` and `set -euo pipefail` so a failed step fails loudly.
- do the real work the instruction asks for, writing every declared output file to its absolute path.
- **pin every pip/uv install with `==`** (solve.sh is one of the four scanned files). apt the right
  way: `apt-get update` → install → `rm -rf /var/lib/apt/lists/*`, no version pins.
- keep it deterministic — no reliance on wall-clock, random seeds unset, or network flakiness. if
  randomness is unavoidable, seed it so the oracle scores 1 repeatably (reference verification runs
  it many times).

### step 3 — make it the honest reference, not a shortcut
solve.sh should solve the task the way the instruction intends — it is the reviewer's proof of
solvability and the anchor for `verification_explanation`. do not special-case the verifier or
write a value the checker happens to accept; it must earn the reward by doing the work.

**drive the real tools.** whatever the instruction names, solve.sh should actually invoke it —
`freecad` headless, the `bun` cli, `psql`, `spark-submit`, `coqc`, real `torch` on cpu. if the
reference can produce the artifact without ever touching the named tool, the tool was decoration
and the anchor rule in [[CLAUDE.md]] is not really satisfied — that is a design signal worth
acting on now, not after a rejection. do not hand-write the expected bytes; make the tool emit
them, the way a person would.

### step 4 — dry-run mentally against the verifier
every output the verifier will read must exist at the right path with the right format after
solve.sh runs. if the verifier compares against sealed ground truth in `tests/`, make sure solve.sh
actually produces a matching result. mismatches here are the #1 cause of oracle ≠ 1.

### step 5 — keep runtime under the timeouts
solve.sh must finish inside `[agent].timeout_sec`, and the verify step inside
`[verifier].timeout_sec`. if solve.sh is slow, raise the timeouts in task.toml (≤ 18000) rather
than cutting corners.

## checklist
- [ ] `#!/usr/bin/env bash` + `set -euo pipefail`
- [ ] writes every declared artifact to its absolute path
- [ ] pip/uv pinned with `==`, apt unpinned + cleaned
- [ ] deterministic / seeded — scores 1 on repeated runs
- [ ] solves honestly, does not special-case the checker
- [ ] **actually invokes the real tools the instruction names; artifact is produced by the tool,
      not hand-written**
- [ ] finishes within the timeouts
