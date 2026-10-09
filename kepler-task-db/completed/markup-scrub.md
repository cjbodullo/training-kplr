# markup-scrub — Software — $175

Submitted 2026-07-30, id `e4V8bXqvXyOaP6ZBbhxN`. Passed the full automated
pipeline, awaiting human review.

## what it is

Clone a retired webmail HTML render gate byte for byte. The agent writes
`run(source) -> text` in `/app/scrub.py`. The mechanism is published in full in
`MX9.md` and already implemented in the shipped stub, including the reader and
writer (`htmlkit.py`), so there is no scaffolding to rebuild and no
serialisation trivia to lose on. Sixteen conditional policy decisions are
withheld. The real unit is still up as a sidecar, metered at 200 nodes for the
whole engagement, refused whole on overrun, never refilled. Graded byte exact,
all or nothing, over 40 sealed bodies.

## result

    easinessProbe     passed   1/3
    difficultyProbe   passed   5/8  in_band   rewards 0,1,1,1,0,1,1,0
    trajectoryReview  pass     failureModes []   all 4 blocking criteria 0/8
    trial durations   29 to 36 minutes against a 14400s budget

## what it took to get there

v1 shipped at a 320 node meter with section 9 written as *leading* questions
that named the candidate condition for each axis. It passed six stages and then
died at the easiness screen, 2 of 3 solved in about 14 minutes a run.

The duration was the diagnosis: the agents were never short of information, so
the budget was not the problem, the manual was. Describing a decision hands over
the shape of the answer, and what is left is a two or three way choice one small
probe settles.

v2 changed two things — section 9 rewritten to name the decision point and stop,
and the meter cut 320 -> 200 — and moved the screen from 2/3 to 1/3 and the
difficulty probe to 5/8 in band.

## caveats for anyone reusing this

- 5/8 is the top of the band. No margin. Build the next one to aim lower.
- `dev/fit_strong.py`, a coordinate descent handed the exact axis list and
  alternative set, put 320 nodes at the 40 percent mark and real agents cleared
  it at 67 percent. Treat that curve as a lower bound on the budget, never as
  the calibration.
- Full detail and every measurement in `task-src/markup-scrub/dev/CALIBRATION.md`.
