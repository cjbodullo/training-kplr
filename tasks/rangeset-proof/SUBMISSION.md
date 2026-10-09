# rangeset-proof — submission sheet

- Task name: rangeset-proof
- Category: Software · Labels: Languages (optionally Algorithms)
- Zip: tasks/rangeset-proof/rangeset-proof.zip (source: task-src/rangeset-proof)
- Author: Anand Pahade <bryandavidson737@gmail.com>
- Agent budget 18000 s, verifier 3600 s, 4 cpu / 8192 MB

Idea check pitch:
Machine-check a frozen C module from a CFDP style file receiver with Frama-C 25.0 WP (Why3 1.5.1, Z3 4.8.12, CVC4 1.8, no Alt-Ergo): a canonical set of half open byte ranges in a 64 slot array with a binary search rs_contains, rs_next_gap, rs_add (insert, merge everything that overlaps or touches, or -1 when full and nothing touches) and rs_discard_below (advance the delivered watermark: drop everything below x, trim the straddler) over a contract-less memmove helper. The header carries full functional ACSL specs. Done = every WP goal Valid with -wp-rte, every loop with a proved variant, C tokens unchanged, no axioms/admit/ghost functions/extra public contracts. Hard because canonical is adjacent-only so transitive order needs induction (ghost loop), the helper contract must be invented in absolute index form to survive struct field aliasing, call arguments wrap in WP's model, and the end-of-path membership and canonical goals never close in place, so the reasoning has to be moved into two-state lemmas proved in isolation. Every failure is an Unknown goal with no counterexample.

Local gates:
- anchor_check: frama-c, z3, cvc4 [NEST], why3 [NE-T] (driven through WP); warnings only.
- metadata_check: clean.
- harbor oracle 1.000 from source (272/272 goals, all 7 tests pass).
- harbor nop 0.000 from source (32/94 goals, 5m23s).
- direct grader: reference 1 (61 s); nop 0; cheats 0: axiom_false, weaken_contracts (requires \false on definitions), ghost_spin (vacuous proof via non terminating ghost loop), code_edit, admit.
- reference timing: 272/272 at -wp-timeout 10, slowest goal ~3.3 s (grader decisive pass uses 60 s).
- harbor oracle 1.000 from the extracted zip as well (2m55s).
- harbor check: NOT completed locally, twice (AgentSetupTimeoutError after 360 s; no Anthropic API key on this box, same infra failure recorded for earlier tasks).

v1 submitted 2026-10-07 22:51: structural, AI check, similarity, reference verification passed; quality review FAILED on
`anti cheat robustness` only (recursive non well founded logic/predicate definitions as a vacuity route).
v2 fix: verifier builds a reference graph over the agent's predicate/logic definitions and rejects any cycle
(self or mutual, labelled or not); instruction states the rule; cheats recursive_logic.c and mutual_predicate.c
added (both 0). Re-verified: reference 1, all 7 cheats 0, metadata clean, harbor oracle 1.000 / nop 0.000 from the
rebuilt zip. Delete the v1 submission before resubmitting (new hash).

v3 (2026-10-08) after the v2 submission PASSED structural/AI/similarity/reference/quality/anti-cheat but FAILED the
easiness probe (claude-opus-5-5 low, 2 of 3 solved: 2h10m and 2h28m, $4.49 / $8.94, 80-120k out tokens; allowed <= 1).
Hardening: added a fourth public function rs_discard_below(s, x) with a full functional header spec (canonical + exactly the
members at or above x). It brings a third mutating proof: ghost induction that everything after the first survivor lies
above x, a trimmed head plus a downward shift described by a two state predicate pair, ~10 new lemmas including a
moved-witness lemma (slot k - i) for the membership back direction. Removed the instruction hint that the callers of
rs_move need a contract. Reference 333/333 goals at 10 s/goal, slowest ~6 s. Grader: loop count 7 + ghost loops, header
postconditions 2/3/5/2, header assigns of rs_add and rs_discard_below, wrapped CSV rows skipped.
A full rs_remove (split/trim, -1 when full) was built and fuzzed but its reference proof was not stable enough
(eight way case selection in the closing lemmas, 30-48 s lemmas, one unprovable), so it was dropped; sources in
task-src/rangeset-proof/dev/archive_remove/.
Local re-verification: direct grader ref 1, nop 0, 8 cheats 0 (axiom, weakened contracts, ghost spin, code edit on rs_add,
code edit on rs_discard_below, admit, recursive logic, mutual predicates); harbor oracle / nop from the rebuilt zip below.
v3 harbor gates from the rebuilt zip: oracle 1.000, nop 0.000, no exceptions. harbor check still not run locally (no API key on this box).
