# stand-down — PASSED ALL NINE GATES 2026-08-03

- v2 `CD1fQeIzNZuUPImdSUr3`, Software / Data engineering + Systems, $175
- status: Needs Review (automated pipeline complete, awaiting human reviewer)
- source `task-src/stand-down`, deliverable `tasks/stand-down/stand-down.zip`

## measured

| probe | result | per-trial | minutes | cost |
|---|---|---|---|---|
| easiness | 1 of 3, passed | 0,1,0 | 8,15,14 | $6.58 |
| difficulty | **2 of 8, in band** | 0,1,0,0,0,0,0,1 | 14-27 | $32.72 |

Reference 504/504. Shipped first pass 30/504. Six cheats 0.

## the two versions

v1 `mMzho9xcPsDX4oDpe0nD` was submitted as **ML / Inference** and failed
`quality_check` on ONE blocking criterion, `category_and_tags`, with the other
thirteen passed. The fix was three lines of task.toml. Nothing else changed —
same instruction, same data, same verifier, same sealed answers. See
[[ml-scenario-is-not-ml-task]].

## core problem, subject stripped

State exactly when an automated decider lost the authority to act on its own,
who it passed to, and what it could still put out meanwhile, where the stand
down conventions are never stated and are proved only by how shipped downstream
programs behaved off the back of a handover.

- withheld kind: ABSTENTION / DEFERRAL AUTHORITY (new)
- deliverable shape: per case a (holder, since, emit) triple (new)
- subject: offshore piling under a marine mammal permit, four species heads
- apparatus: Informix 4GL, IDL x2, IEC 61131-3 structured text x2, PowerScript x2

## the seven readings, ablation over 504 calls

spend 51 · accept 75 · boundary 276 · mask 299 · paired 211 · bridge 73 · chain 57

## what the failing trials actually got wrong

The probe analysis names the misses per reading, which is the ablation index in
`tests/sealed/ablation.json` doing its job. Trial 0 (0 reward, 22 min, wrong on
236 of 504) missed **boundary 198 of 276**, **mask 168 of 299**, **paired 145 of
211**. So the three readings carrying the most weight are the three that break a
strong agent, and the two that solved it got all seven.

## build proofs kept in dev/

- `sweep.py` — 1 of 128 reading settings reproduces the sealed run; 0 of 128
  change the shipped brackhead worked example
- `rivals.py` — four rivals move 30/36/63/340 answers, each settled by a literal
  sentence still in a shipped file
- `audit.py` — 31 citations, every reading pinned in >=2 files, cap 4 per file
- `verify_pair.py` — reference == engine at the site's reading, first pass ==
  engine at the flat reading
