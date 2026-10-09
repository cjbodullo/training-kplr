# braid-submit — ML / Evaluation — all nine gates passed 2026-08-01

Submission `hl1vYc6IOUtDlb6Nt7Td` (v2). Awaiting human review.

difficultyProbe 1 of 8 `in_band`; easinessProbe 1 of 3; every other gate green.

## the task

Second home for the verdict-graded acceptance authority family, first in ML.
A lab in a bespoke evaluation consortium (the braid assembly) is coming off
probation. Thirty eval campaigns ship in `/app/season`; the agent must author
the submission the sealed assessor seats for each, first time, into
`/app/submissions.json`. The pack publishes the document, the arithmetic and
all seventeen notice codes; `selfcheck.py` settles ten of them exactly and
declines the other seven. There is no assessor in the container.

Deliverable is DATA, so the verifier `json.loads` only and runs no agent code.
That is why `cheatProbe` was clean on both versions.

## the two versions, which are a controlled experiment

Identical except the evidence layer.

| | easiness | difficulty |
|---|---|---|
| v1, four classifier functions | 3 of 3, 450-472 s | not reached |
| v2, day book + board pack | 1 of 3 | 1 of 8, in band |

v1 shipped `scrap()` (filtered on build and draw), `unbacked()` (computed the
pre-hotfix condition), `worklist()` (composed them) and `figure_of()`
(recomputed the figure over seated chapters). v2 replaced all four with a
68-entry dated day book generated from the real campaign records, plus a
rendered board-pack extract from a retired campaign whose published 69.3
service level and 6667 figure settle two readings by arithmetic.

## local evidence

oracle 1.000 and nop 0.000 from the source tree and the extracted zip; 8 cheats
all reward 0 through the real verifier image; 7476 perturbations of the seated
submissions, none cleared; `dev/audit.py` clean.
