---
name: kepler-environment
description: Step 3 of Kepler task authoring. Build the agent environment/ (Dockerfile, optional compose and data) with realistic starting state, correct apt/pip hygiene, and zero references to solution/ or tests/.
---

# Kepler Environment — SKILL

**pipeline position:** step 3 (build). prev → kepler-instruction. next → kepler-solution.

build `environment/` — the container the agent works in. this is the ONE place that must never
reference solution or test files: anything the agent can read here it can use, so a leak = the
answer is out.

## output
- `task-src/<slug>/environment/Dockerfile`
- `task-src/<slug>/environment/docker-compose.yaml` (optional, multi-container only)
- `task-src/<slug>/environment/data/...` (optional, COPY'd into the image)

---

## workflow

### step 1 — design the starting state
what does the agent see at t=0: source tree, datasets, services, seed files. it should be the
honest starting point of the real job — no ground truth, no hidden hints, no partial answers.
put input data under `environment/data/` and `COPY` it into the image.

the starting state should look like a real working checkout of the real tool: the tool installed
the way people install it, its real config files where it really puts them, real input data in the
format it really reads. an agent that has used this tool before should recognise the box.

### step 1b — install the real tools (the anchor lives here)
this is where "represent real computer work" stops being a slogan. the tools named in
`instruction.md` must actually be installed in this image, at the versions the instruction states.

- **install upstream, not a reimplementation.** apt/pip/npm/cargo/upstream release tarball —
  whatever a practitioner uses. `apt-get install -y freecad`, `pip install torch==2.4.0`,
  `npm install -g bun@1.1.30`, the official postgres/memcached image as a sidecar.
- **do not ship a stub where a real tool belongs.** a hand-written 300-line "simulator" of a tool
  that exists upstream fails the anchor rule in [[CLAUDE.md]] and usually reads as artificial
  difficulty on top: the agent ends up reverse-engineering us instead of doing the job.
- **write your own code only for the bespoke part** — the workload, the constraints, the harness
  that drives the real tool. that code is fine and expected. the line is: real tool underneath,
  our problem on top.
- **versions must be reachable offline.** `allow_internet` is never set, so anything the agent
  needs at runtime has to be baked into the image at build time. pull data, models, packages and
  fixtures during the build.
- **the version has to match the instruction.** if you bump a pin here, go fix `instruction.md` in
  the same edit — a mismatch is a spec ambiguity the run audit will find.

**pinning gotcha — apt cannot be pinned, so pin somewhere else.** the format rules forbid apt
version pins, which collides with wanting a known tool version. resolve it in this order:
1. pin the **base image tag** and let the distro release fix the apt version
   (`FROM debian:bookworm-slim` → whatever freecad bookworm ships). state *that* version in the
   instruction, after checking it in the built image.
2. prefer an ecosystem that does allow pins — `pip install torch==2.4.0`,
   `npm install -g bun@1.1.30`, `cargo install --version`. pip/uv **must** be pinned with `==`
   anyway; this file is one of the four scanned.
3. for tools with neither, `COPY` a fetched upstream release tarball from `environment/data/` and
   unpack it — version is then whatever you vendored, and it stays reproducible offline.
never work around this by apt-pinning; the static check rejects it outright.

if no real tool fits the design, that is not an environment problem — go back to [[kepler-idea]]
step 1b, because the idea is aimed at an invented world.

### step 2 — write the Dockerfile
- pick a concrete base (no `FROM --platform=` pins). pin a specific tag for reproducibility.
- install system deps with apt the correct way — **no version pins on apt**:
  ```dockerfile
  RUN apt-get update && apt-get install -y --no-install-recommends <pkgs> \
      && rm -rf /var/lib/apt/lists/*
  ```
- **pin every pip/uv install with `==`** (this file is one of the four scanned files).
- set a sane `WORKDIR` (commonly `/app`) matching the absolute paths in the instruction.
- leave the agent real work to do — do not pre-solve, do not stage output files.

### step 3 — verify zero leakage
the environment must not reference, contain, or hint at anything in `solution/` or `tests/`:
- no ground-truth values, expected outputs, or checker logic baked in.
- no comments describing the intended approach.
- `solution/` is mounted only for the oracle run; `tests/` is a separate image the agent never sees.
  keep it that way — nothing in `environment/` may point at either.

### step 4 — optional sidecars (multi-container)
if the task needs live services (db, queue, mock api), add `environment/docker-compose.yaml`:
- **NO volumes at all** — named *and* bind both fail validation now (this changed; named volumes
  used to be allowed). bake shared files into each service's image at build time and pass runtime
  state between services over the compose network. a sidecar that needs durable state keeps it
  inside its own container filesystem for the life of the run.
- sidecars are for realistic environment difficulty (live traffic, stateful services), not for
  hiding answers.
- a GPU task (`gpus = 1`) **cannot** use compose at all — pick one or the other.
- **use the real upstream images** — `postgres:16`, `memcached:1.6.21`, `redis:7.4`, `mysql:8.4`.
  a sidecar is the cheapest way to anchor a task in real software: the agent talks the real wire
  protocol to the real server and gets the real errors back. a mock service you wrote is the
  opposite, and only earns its place when nothing real exists for that role.

### step 5 — size the resources in task.toml
set `[environment]` limits to what the build + task actually need (defaults: 1 cpu, 2048 MB,
10240 MB storage, 600s build). raise for compute/data-heavy work, but **cpus and memory_mb are
standard sizes only, not caps** — `cpus` ∈ {1,2,4,8,16}, `memory_mb` ∈ {1024,2048,4096,8192,16384},
`storage_mb` ≤ 40960. an in-between value (6 cpus, 3072 MB) is rejected at the structure check.
never add `allow_internet`.

`gpus` stays `0` **unless** this is an ML task submitted with the GPU option. then set `gpus = 1`
(one is the maximum) and pin exactly one class, `gpu_types = ["H100"]`, so every trial runs on the
same card. two constraints come with it: no `docker-compose.yaml`, and the GPU attaches to the
environment itself — containers the agent starts inside it do not inherit one.

## checklist
- [ ] **every tool named in instruction.md is actually installed here, at the stated version**
- [ ] **installed from upstream (apt/pip/npm/tarball/official image), not reimplemented as a stub**
- [ ] **any code we wrote is the bespoke workload on top, not a stand-in for a real tool**
- [ ] **everything needed at runtime is baked in at build time (no internet at run)**
- [ ] realistic t=0 state, real work left to do (not pre-solved)
- [ ] no reference to solution/ or tests/, no ground truth, no approach hints
- [ ] apt: `update` → install → clean, no version pins
- [ ] every pip/uv pinned with `==`
- [ ] no `FROM --platform=`, concrete base tag
- [ ] compose (if any) declares **no volumes of any kind**, and the task is not a GPU task
- [ ] `[environment]` cpus/memory on the standard sizes, storage ≤ 40960, no allow_internet
- [ ] `gpus = 0`, or `gpus = 1` + one `gpu_types` class for a GPU-option ML task
- [ ] no `harbor-canary` marker anywhere in the bundle
