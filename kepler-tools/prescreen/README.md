# prescreen — real-agent difficulty screen before submitting

Why this exists: `exact-unlearn` (2026-07-30) shipped on scripted ablations that showed
every partial solution scoring zero, then the pipeline's easiness probe solved it **3 of 3
in 18 to 42 minutes**. Ablations measure whether a *wrong* engine fails. They do not
measure how fast a competent solver finds the right one, and that is the number the
easiness and difficulty probes actually grade.

The screen is one subagent per attempt, given exactly what a real agent gets and nothing
more, then graded through the bundle's own verifier.

## procedure

1. `python3 kepler-tools/prescreen/prep.py task-src/<slug> --out <workdir>` builds a
   clean workspace: the environment tree exactly as the image would lay it out, plus
   `INSTRUCTION.md` (the real `instruction.md`, verbatim), and nothing from `solution/`,
   `tests/` or `dev/`.
2. Spawn one subagent per attempt with the prompt in `prompt.md`, pointed at the
   workspace. No hints, no pointers to the intended approach, no mention of what the
   verifier checks beyond what the instruction says. Give it the same shape of budget the
   probe gives (the probe's trials on exact-unlearn ran 18 to 42 minutes and cost
   $1.75-$4.02, so a screen attempt that stops early is itself a signal).
3. Grade each attempt with the real path: copy its deliverable into a `/app` mount and run
   the tests image, exactly as `dev/run_cheats.sh` does.

## reading the result

- **any attempt solves it, and quickly** -> below the bar. Redesign before submitting.
  Speed matters as much as success: solved-in-20-minutes means there is no headroom to
  recover by adding instances or tightening a cap.
- **no attempt solves it** -> do not celebrate. Read per-attempt partial counts. A run
  that got 90 of 96 exact is a near miss and the task is probably in band; a run that
  never produced a working artifact may mean the task is unsolvable or the scaffolding is
  missing, which fails just as hard.
- **attempts fail for reasons the instruction caused** (ambiguity, missing context, a
  broken practice kit) -> fix the bundle, not the difficulty.

## honesty rule

Record the screen result in `kepler-task-db/` whether or not it flatters the design, and
if no screen was run, say so in `SUBMISSION.md` instead of implying the difficulty was
measured.
