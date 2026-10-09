# Frontier Bench Task Authoring

You help a domain expert author **Frontier Bench** tasks. Each task is one self-contained
**harbor bundle** — an instruction, a containerized environment, a reference solution, and a
sealed verifier that grades pass/fail (exactly 0 or 1). The full spec lives in
[instructions.md](instructions.md) — that file is the source of truth. This workflow turns that
spec into a repeatable, skill-driven pipeline.

Payout: **$300** (Science · Software · ML) or **$200** (Operations · Security · Hardware · Media)
per approved task. Approval requires passing the whole automated pipeline plus human review.

---

## Directory Structure

| Directory / File | Purpose |
|---|---|
| `CLAUDE.md` | Core rules (this file). Always loaded. |
| `instructions.md` | The official spec. Source of truth. Never edit. |
| `kepler-idea/` | Idea pitch + scoring vs the acceptance rubric + difficulty bar. SKILL.md inside. |
| `kepler-instruction/` | Writing `instruction.md` (human-authored, AI-check safe, required suffix). SKILL.md inside. |
| `kepler-environment/` | Building `environment/` (agent Dockerfile, compose, data — no answer leaks). SKILL.md inside. |
| `kepler-solution/` | Writing `solution/solve.sh` (oracle must score 1). SKILL.md inside. |
| `kepler-verifier/` | Building `tests/` (test.sh, Dockerfile, reward.txt, CTRF, anti-cheat, cheat/). SKILL.md inside. |
| `kepler-validate/` | Local gates: harbor oracle / nop / check. Iterate to green. SKILL.md inside. |
| `kepler-submit/` | Final checklist + zip + record. SKILL.md inside. |
| `kepler-api/` | Automate the AfterQuery pipeline (idea check, submit, poll, delete+rebuild+resubmit loop). SKILL.md inside. |
| `kepler-task-db/` | Persistent data: `ideas.md`, `submitted.md`, `completed/`. SKILL.md inside. |
| `kepler-tools/` | Automation code: token bridge extension, `token_write.js` token server, `kepler_api.py`, `kepler_run.py` (loop), `bundle.py`, `rebuild_aicheck.py`, `anchor_check.py`. |
| `tasks/` | Deliverables — one subdir per task (`tasks/<slug>/<slug>.zip` + `SUBMISSION.md`). |
| `task-src/` | Editable bundle source — one subdir per task (`task-src/<slug>/`); the loop rebuilds the zip from here. |

---

## Core Rules

### The two things that fail most bundles

1. **Binary reward contract.** The verifier writes `/logs/verifier/reward.txt` containing exactly
   `0` or `1`, plus a CTRF report (pytest with `pytest-json-ctrf`). **Every** code path — including
   crashes — must still produce a reward. There is no partial credit.
2. **Answer isolation.** Ground truth and grading logic live **only** in `tests/`. Nothing in
   `environment/` may reference solution or test files — that leaks answers and fails validation.
   The verifier must demand real execution evidence, not exit codes or agent-writable state.

### The difficulty band (hard gate)

8 independent frontier-agent attempts run at the full time budget. The task must be solved
**at least 1 and at most 7 times**. Never solved = treated as unsolvable (fail). Solved 8/8 =
below the bar (fail). The band is wide, so the live risk is the *bottom* edge — bias hard, and
never trim difficulty to dodge a 6. (The spec's pipeline list no longer shows a separate
easiness probe; treat that as unconfirmed until a submission proves it.)

Aim for genuinely hard *work*, never artificial difficulty (no trivia, no tokenizer
tricks, no withholding info an expert would obviously have). The internet is open, so
**the solution must not be findable online**.

### Real-world tool anchoring (local policy — no longer in the spec)

The spec dropped this requirement and the pipeline does not enforce it. We keep it: anchored tasks
read as real work to the quality reviewer and give the verifier real version behaviour to grade.
`kepler-tools/anchor_check.py` is our gate, not theirs.

Your role is to represent **real computer work**, not simulated environments. Every task must be
anchored in named software, tools, and artifacts that exist in the world and that a practitioner
would actually touch — FreeCAD, memcached, bun, a MySQL→Postgres cutover, vLLM streaming, Next.js,
React, Coq/Lean, Spark, UEFI, PyTorch. Name the tool, pin its version, install it in the
environment, drive it in the solution, and grade its real output format in the verifier.

Never write "a program", "the software", "a custom framework", "a simulator" where a real tool
belongs. A bespoke in-repo simulator standing in for a real toolchain, or a synthetic world whose
only artifacts are invented file formats, does not count as anchored — no matter how hard it is.

**This does not conflict with "the solution must not be findable online."** Novelty lives in the
*problem you pose on top of real tools* — the workload, the constraints, the data, the failure the
agent has to chase — not in inventing a fake tool. Real toolchain, bespoke problem. If the bespoke
part is the tool itself, you have replaced real work with a puzzle, and the difficulty you measure
is the agent reverse-engineering your invention.

Concretely, an anchored task can point at: real binaries/CLIs and their real flags, real file and
wire formats (`.FCStd`, ELF, parquet, protobuf, the memcached text protocol), real config and
build systems, real APIs and their real error surfaces, real upstream bug/version behaviour. If
you cannot name at least one such tool the task genuinely depends on, the idea is not ready.

### Non-negotiable format rules (static checks reject these instantly)

- **Instruction suffix.** `instruction.md` ends with a blank line, then exactly this sentence
  (N = integer value of `[agent].timeout_sec`), then at most one trailing newline:
  `You have N seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.`
- **Pin pip, never pin apt.** Every `pip`/`uv` install in the four scanned files
  (both Dockerfiles, `test.sh`, `solve.sh`) must pin with `==`. Canonical verifier pins:
  `pytest==9.1.1`, `pytest-json-ctrf==0.5.2`. Apt: `apt-get update` → install → `rm -rf /var/lib/apt/lists/*`, **no version pins**.
- **Verifier is separate.** `[verifier] environment_mode = "separate"`. Bake tests with `COPY . /tests/`,
  pre-install all verifier tooling in the image (never install inside `test.sh`), and
  `RUN mkdir -p` the parent dir of every declared artifact.
- **Environment policy.** Never set `allow_internet` (either value). No `FROM --platform=`.
  Timeouts ≤ 18000s. `cpus` and `memory_mb` take **standard sizes only** — cpus ∈ {1,2,4,8,16},
  memory_mb ∈ {1024,2048,4096,8192,16384}; `storage_mb` ≤ 40960.
- **GPUs.** `gpus = 0` unless it is an ML task submitted with the GPU option; then `gpus = 1`
  (one is the max) and pin exactly one class, `gpu_types = ["H100"]`, so every trial runs on the
  same card. A GPU task cannot use `environment/docker-compose.yaml`, and containers started
  inside the environment do not inherit the card.
- **No canary markers.** A `harbor-canary` GUID line anywhere in the bundle is an instant reject.
- **Task name.** `[task].name = "afterquery/<slug>"`, slug lowercase, ≤ 3 hyphen-separated words,
  equal to the submitted task name.
- **Absolute paths.** Reference every expected output file explicitly and absolutely (e.g. `/app/output.json`),
  and declare verifier-read paths in top-level `artifacts = [...]`.
- **Compose.** Optional `docker-compose.yaml` may add sidecars, but **volumes of any kind — named
  or bind — fail validation**. Bake shared files into each service's image and pass runtime state
  between services over the compose network.

### Authorship

- Write `instruction.md` **yourself, in your own words** — an AI check screens every instruction file.
  AI help on scaffolding, test-data generation, environment code is fine; the instruction is not.
  Use the humanization writing rules (lowercase, terse, no em dashes, no hyphens, dropped articles) —
  see `kepler-instruction` steps 5-6. Casing alone is NOT enough: a tidy lowercased spec failed the
  AI check twice. Detectors key on structure and rhythm, so also write with real burstiness (mix
  very short and long sentences), prose instead of neat `##` sections and parallel bullets, and a
  first-person voice. `kepler-instruction/humanize.py` (humanizeai.pro client) rewrites prose into a
  passing voice — but it SCRAMBLES protected code tokens and can invert meaning, so a manual
  correction pass against the draft is mandatory, followed by a human edit pass. Keep code
  identifiers, literal values, paths, and the required suffix exact.
- Submit original work — compared semantically, verbatim, and by environment structure against the
  public task set, all submissions, **and your own back catalogue**. Near-duplicates are rejected,
  including a rebuild of your own earlier task under a new domain. A byte-identical resubmit is
  blocked outright by content hash.
- **New problem, not new subject matter.** Swapping the domain nouns, renaming the files and
  rewording the brief around the same scaffold, the same reference solution and the same verifier
  shape is a rebuild, and it is rejected however thoroughly the surface was changed. The more
  tasks built on one pattern, the further the next one has to sit from them.
- **Target a different failure mode each time.** Before building, name what specifically the agent
  will get wrong — a race it cannot see, an invariant it will not preserve, a rule it has to infer
  rather than read — and check it is not what the last few tasks tested. The spec names our exact
  habit: tasks that all reduce to reconstructing the numbers a missing tool would have produced
  are worth about as much as one, whatever the setting. Volume is not the goal.

---

## Workflow (end to end)

### plan
1. **kepler-idea** → pitch the idea, name the real tools it rides on, score it against difficulty /
   verifiability / specificity, confirm domain + payout tier, log to `kepler-task-db/ideas.md`.
   (Idea check is advisory.)

### build the bundle (in `task-src/<slug>/`)
2. **kepler-instruction** → write `instruction.md` (human voice, names the real tools + versions) +
   `task.toml` metadata skeleton.
3. **kepler-environment** → build `environment/Dockerfile` installing those real tools at pinned
   versions (+ optional compose/data).
4. **kepler-solution** → write `solution/solve.sh` and helpers, driving the real tools.
5. **kepler-verifier** → build `tests/` (test.sh, Dockerfile, ground truth) grading the tools' real
   output formats + `cheat/` attempt.

### prove it
6. **kepler-validate** → `harbor run -a oracle` (=1), `harbor run -a nop` (=0), `harbor check`.
   Iterate on any red gate; loop back to the relevant build skill until all three are green.

### ship
7. **kepler-submit** → final checklist, zip the bundle, submit with category + labels, then
   record the task in `kepler-task-db/`.

### automate (optional)
8. **kepler-api** → drive the whole cycle via the API instead of the web UI: idea check, submit,
   poll the pipeline live, and on a verdict failure delete + rebuild + resubmit in a loop until it
   passes. Needs the token bridge running (`pm2 start kepler-tools/ecosystem.config.js` + the extension).
   `python3 kepler-tools/kepler_run.py loop --zip tasks/<slug>/<slug>.zip --name <slug>
   --category <Cat> --labels a,b --src task-src/<slug>`.

---

## The 7 domains (pick exactly one; must match in the submit form and `[metadata].category`)

`Science` · `Software` · `ML` · `Operations` · `Security` · `Hardware` · `Media`.
Labels (subcategory) are listed per domain in [instructions.md](instructions.md); pick **one or two** at submit,
set `[metadata].subcategory` to the closest one. Lean into your strongest domain — a couple of
genuinely hard tasks from deep expertise beat a pile of shallow ones.

## Local validation commands (must all pass before submit)

```bash
# anchor scan first (cheap, no docker) — real tools named + installed, no generic placeholders:
python3 kepler-tools/anchor_check.py task-src/<slug> --tools memcached,pymemcache

# from the bundle source dir (task-src/<slug>/), with docker running:
harbor run -p . -a oracle -e docker          # reference solution must score exactly 1
harbor run -p . -a nop -e docker             # doing nothing must score exactly 0
harbor check . -m anthropic/claude-opus-4-8  # LLM review against the implementation rubric
```

## User Preferences

- This workflow is iterative. First version is a draft — expect to refine each skill on feedback.
- Prefer concise, direct communication.
