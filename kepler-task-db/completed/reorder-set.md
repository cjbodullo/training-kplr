# reorder-set — PASSED ALL NINE GATES

**Software / Systems + Algorithms** · `rylkLSJ71PvBhl5sQKUS` · 2026-08-03 · Needs Review

easiness 0/3 · **difficulty 3/8 (band 1-6)** · trials 1342-1647s · structure, aiCheck,
similarity, oracleNop, qualityCheck, cheatProbe, easinessProbe, difficultyProbe,
trajectoryReview all green.

## Core problem
Say what a machine **may** observably do. A bespoke dual-pair quad-core part (Tolven) in a
small-satellite instrument controller; the B0 silicon is on the validation rig and nobody at the
firm has a board. The agent writes `/app/outcomes.json`: for each of 48 sealed straight-line
concurrent sequences, the exact set of final register-and-memory states B0 can produce. Exact set
equality on all 48 at once, so an outcome listed that cannot happen fails as hard as one missing.

## Final shape
- **Published whole**: instruction set, locations, register map, fabric, one queue per pair,
  writes posted in issue order, one-location-one-order, SYNC, the branch shadow, a word read
  waiting for a queued byte write, the whole harness, and `sim/model.py` as a complete correct
  model of the *previous* revision that reproduces all ten bench captures.
- **Withheld**: 10 readings across 12 bits. Three contradict every part in the public
  literature — a branch that holds reads, a write queue that does not preserve its order, and a
  pair that is not multi-copy atomic.
- **Evidence**: four defect write-ups, a register index giving nine more items as title +
  disposition + build number only, and barrier placement across Ada flight software, a Forth
  PROM monitor and a printed sheet. None of it runs in the container.

## The six rounds, and what each measured
| v | change | result |
|---|---|---|
| 1 | 8 readings, 6 canonical, mechanism spelled out in bus-monitor annexes | easiness 3/3 |
| 2 | annexes cut, axis checklist cut, 3 anti-lore readings | difficulty 0/8 — my note contradicted my model; 6 of 8 trials scored 32/36 |
| 3 | contradiction removed + swap counterweight | easiness 3/3, 11-13 min |
| 4 | 5 readings demoted from stated symptoms to barrier placement | easiness 2/3 |
| 5 | machine extended: HOLD barrier + byte accesses, 48 sequences | **easiness 0/3**, difficulty 0/8 at 44-46 of 48 |
| 6 | restored ONE defect write-up (the swap latency entry) | **easiness 0/3, difficulty 3/8, PASSED** |

Pass rate by round: ~1.0, —, ~1.0, ~0.67, ~0.0, **0.375**.

## The reusable results
1. **Contradict the lore, do not outnumber it.** With a public reference model (a real ISA),
   canonical readings are free at any k. v1→v5 fixed this by making the machine differ.
2. **Per-reading hit rates across trials are measured probabilities.** v5's misses were two
   readings at ~0% and ~25%. Fixing both would have landed ~8/8; fixing only the ~0% one put the
   pass rate at the other's 0.25. Predicted 2 of 8, got 3.
3. **Identifiability by exhaustive sweep**: of all 4096 readings of the twelve open bits, exactly
   one reproduces the sealed sets, no twins, nearest wrong reading still wrong on 2 sequences.
4. **Inert readings are invisible except to ablation**: write merging (0/36), barrier queue scope
   (0/48) and `hold_waits_queue` (0/48) all had to be thrown away or published.
