# spool-runner — Software / Systems — Needs Review

- **submission**: `Z3jG66DyfaPltAaElqLN` (v4), 2026-07-30
- **payout tier**: $175 (Software)
- **verdict**: all 8 gates passed. `difficultyProbe: in_band, 4 of 8`. `easinessProbe: 0 of 3`.
- **source**: `task-src/spool-runner/`, bundle `tasks/spool-runner/spool-runner.zip`

## What it is

Metered clone of the outbound delivery policy of a mail appliance, the "Perrin R-9".
`PERRIN.md` publishes the entire mechanism and `/app/spool.py` ships it as running code;
**twelve** conditional decisions are withheld and listed as twelve numbered questions.
The only oracle is the live unit on a compose sidecar, metered at 500 units (one per
event printed, truncating rather than refusing, persisted across restarts). Graded
byte-exact on 40 sealed traces, all or nothing.

## Calibration history — the count was the dial

| build | k | verdict | agents got right | graded matches |
|---|---|---|---|---|
| v1 | 17 | `too_hard 0/8` | 13–16 of 17 | 0–6 of 40 |
| v2 | 14 | `too_hard 0/8` | 11–13 of 14 | 2–25 of 40 |
| v4 | 12 | **`in_band 4/8`** | — | — |

Neither zero was a wall. In both failures every trial ran to a natural finish, spent
480–500 of the 500 meter units, reproduced its own purchased probe logs exactly, and
passed all six analysis checks (`task_specification`, `reward_hacking`,
`difficulty_crux`, `near_miss`, `refusals`, `low_timeout`). All-or-nothing pass rate is
p^N, so the count bound it, not the meter and not the spec.

**The method that worked.** Rather than guessing the next k, tally which decisions the
failing trials actually got wrong, from `analysis.jobSummary`. Over v2's eight trials:
per-domain transaction cap wrong in 5, message ordering in 4, give-up count 3, lifetime
2, batch threshold and split threshold 1 each. Publishing the top two clears every miss
in trials 0, 2, 5, 6 and leaves 1, 3, 4, 7 still wrong — **projected 4 of 8, landed 4 of
8.** Publishing only the cap projected 2 of 8; the pair was chosen because binomial noise
around p=0.25 lands 0/8 about a tenth of the time versus under 1% around p=0.5.

Meter, seeds, generator and verifier were byte-identical across v2 and v4, so decision
count was the only variable that moved.

## Similarity block (cost two rounds)

v3 blocked at `similarity` twice, `matches: []` and `redacted: true`. Not index lag — a
40 minute settle window changed nothing, and v1→v2 had been a near-identical resubmit
seconds after deletion that passed. Cause was that every parallel session had converged
on one opening beat: a retiring vendor appliance whose behaviour must be cloned because
downstream was fitted to it. `crash-bucket` shared "goes back to the leasing company at
the end of the quarter" verbatim; `markup-scrub` was a *mail* appliance with the same
beat and landed in the corpus between v2's pass and v3's block.

Fixed by reframing the story only — from "clone the retiring box" to "stand a second
spool beside the live one on the same queue" — plus the matching `relevant_experience`.
Mechanism, environment and verifier untouched. Passed on the next submission.

## Final numbers

- ablation: each of the 12 decisions moves 9–40 of the 40 graded logs on its weakest alternative
- designed campaign: 7 traces / 177 units covers all 25 decision-alternative pairs (meter 500 = 2.8x)
- grinder at 500 units: 0–2 of 12 wrong on designed probes, 1–5 on estate traffic
- example traces cost 3789 units if posted, 7.6x the whole meter
- local gates: oracle 1.000, nop 0.000, reference 40/40, stub 0/40, variant equivalence over 1240 traces
