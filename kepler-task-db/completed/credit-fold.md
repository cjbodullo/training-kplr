# credit-fold — ML / Training — PASSED ALL NINE GATES 2026-08-03

`y27BJJSzBmPrpEmtQZ1b`, status **Needs Review**, awaiting human review.

| gate | result |
|---|---|
| structure | passed |
| aiCheck | passed, first try, hand written, no humanizer |
| similarity | passed (see the v1 block below — this is the whole lesson) |
| oracleNop | passed |
| qualityCheck | verdict **pass**, 35 criteria, 0 findings |
| cheatProbe | passed |
| easinessProbe | **0 of 3**, trials 703 / 514 / 697 s |
| difficultyProbe | **3 of 8, band in_band** (lo 1, hi 6), $40.94 |

Trials: 0,0,**1**,0,0,**1**,0,**1** at 930-1424 s of a 14400 s budget, $3.62-6.38.

## The task

Core problem, subject stripped: *decide what counts as an ending, and what each
ending is worth* — the episode boundary and delivery semantics of a distributed
rollout log, folded into the learning targets an offline update consumes.

**Lane: reinforcement learning, which was 0 hits across 241 local instructions**
(reinforcement / replay buffer / policy gradient / bandit / curriculum all 0;
rollout's 4 hits were all deployment-rollout). Subject: RL aeration blower
control on five activated sludge lanes at a water recycling centre, so
terminate-vs-truncate is native to the plant rather than bolted on.

Deliverable is a **program**: the agent finishes `/app/fold.py` and the verifier
runs it over three windows it has never seen, comparing 4621 returns, all or
nothing.

## The six graded readings

The RL arithmetic is published in full (gamma 31/32, horizon 8, floor at every
step, worked example, file contract). What is withheld is what the log *means*:

1. a run of control carries on across a lease handover and a build swap
2. a `HAND` close is worth the frame's recorded forward estimate; `TRIP` and
   `STORM` are worth nothing
3. `blend` (coagulant cost, dosed off a panel the controller has no line to) is
   not reward
4. `lock` (the interlock charge) is reward
5. the interlock charge is carried back two ticks, onto the frame whose setpoint
   took the lane under the floor
6. where the bus brought a frame twice, the first arrival stands

Ablations over the 4621 graded returns: blend 2169, copy 590, latch 397 (358 for
a one tick miss), lock 319, close 168+104, seam 112+104. Shipped draft agrees on
1476 of 4621.

## Why it cleared similarity, which is the transferable part

**v1 (`Jk0bnvwbXBbceUWsw7Ek`) was blocked at similarity on a first submission**
with structure and aiCheck already green. The core problem was fresh; the **job
shape** was not — "produce the corrected training data as a JSON file,
conventions proved by unrunnable consumers" is my dominant family, and
`asof-entitle`, also ML/Training, went live the same morning.

v2 changed **what is measured**, not the surface: data file -> program graded on
unseen windows. The mechanism, the estate, the six readings and the reference
engine were byte identical across both rounds, so this is a controlled
measurement. Written up as memory `program-deliverable-clears-a-job-shape-twin`.

## The infra round

The first v2 run returned `failureKind: infra` at difficulty_probe with
`band: None`, because 4 of 8 trials threw `UnknownApiError`. The tally underneath
was **1 of 8** — already in band. Diagnosed as a time localised platform flake,
not bundle specific: errored trials spanned 0.8M-3.0M tokens while completed ones
spanned 2.5M-6.1M, credit-fold was the only infra failure in a 99 task queue, and
only 15 of 760 recorded trials queue wide ever carried an exception. Deleted,
backed off 300s, resubmitted **unchanged** rather than editing a task that was
already reading in band. The clean rerun returned 3 of 8.

## Standing guards in the bundle

* `dev/checks.py` — the quiet stretch must settle the arithmetic, the coverage
  rule and the free readings, and must be inert for all nine graded flips, while
  every graded flip moves >= 30 returns in every sealed window
* `dev/rivals.py` — 171 rivals over the whole space of every axis; every one that
  moves a figure must sit on an axis `dev/audit.py` holds citations for
* `dev/audit.py` — 28 citations over 8 readings in 8 files, none held up by the
  runbook alone, plus a banned gloss scan
* `dev/verify_pair.py` — reference == sealing engine over all five windows
* seven cheats, all 0, including `c7_escape` which runs inside the graded run and
  goes after `/tests/sealed/answers.json`, the variants file and the pytest cwd
