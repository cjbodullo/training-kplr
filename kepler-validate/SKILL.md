---
name: kepler-validate
description: Step 6 of Kepler task authoring. Run the local gates (real-tool anchor scan, then harbor oracle=1, nop=0, check) and iterate to green, looping back to the responsible build skill on any red gate. Includes a docker-less pytest venv fallback.
---

# Kepler Validate — SKILL

**pipeline position:** step 6 (prove it). prev → kepler-verifier. next → kepler-submit (manual) or
[[kepler-api]] (automated submit + poll + rebuild loop).
loops back to any build skill on a red gate.

run the local gates. the pipeline runs the harbor ones on the real harness, so a local failure is a
guaranteed pipeline failure. gate 0 (anchor) is ours, not the pipeline's — it protects the rule the
pipeline only catches later, in quality review and human review, at the cost of a round trip. do
not submit until all four are green.

## prerequisites
- docker running
- harbor installed: `uv tool install harbor`
- run all commands from the bundle source dir `task-src/<slug>/` (holds instruction.md, task.toml,
  environment/, solution/, tests/, cheat/). harbor ignores the extra source-only files
  (`required_tokens.txt`, `last_failure.md`); the clean deliverable zip is built separately by
  `kepler-tools/bundle.py`.

---

## the gates

### gate 0 — real-tool anchor scan (cheap, no docker)
```bash
python3 kepler-tools/anchor_check.py . --tools <comma,separated,tools>
```
mechanical half of the anchoring rule in [[CLAUDE.md]]: are the tools the instruction names
actually installed in `environment/`, driven by `solution/`, and used by `tests/`; does anything
get installed that the instruction never mentions; did a version drift between the Dockerfile and
the instruction; is there generic placeholder phrasing ("a program", "the tool") where a real name
belongs. errors exit 1, warnings exit 0 unless you pass `--strict`.

run this first because it costs a second and it fails for reasons docker cannot see. the columns
map straight back to a skill: `N` missing → [[kepler-instruction]], `E` missing →
[[kepler-environment]], `S` missing → [[kepler-solution]].

the scan is mechanical and cannot judge the part that matters. do that yourself, once, out loud:
**if i swapped the named tool for a 200-line stub, would the difficulty change?** if the answer is
no, the anchor is decoration and the fix is upstream in [[kepler-idea]] step 1b, not here. a bundle
that passes all three docker gates can still be the wrong task.

### gate 1 — oracle scores exactly 1
```bash
harbor run -p . -a oracle -e docker
```
the reference solution (`solution/solve.sh`) runs against the untouched environment; reward must be
`1`. if not:
- oracle produced wrong/missing artifact → fix `kepler-solution` (paths, format, determinism).
- verifier rejects a correct solution → fix `kepler-verifier` (too strict, wrong ground truth, path mismatch).

### gate 2 — nop scores exactly 0
```bash
harbor run -p . -a nop -e docker
```
doing nothing must score `0`. if it scores `1`, the verifier is passing on the empty/starting state
— it is not actually checking the work. tighten `kepler-verifier`. also re-check the environment
does not already contain the answer (`kepler-environment`).

### gate 3 — quality check passes
```bash
harbor check . -m anthropic/claude-opus-4-8
```
LLM review against the implementation rubric (instruction completeness, verifier rigor,
determinism, environment hygiene, metadata quality). address every blocking finding; note advisory
ones for the human reviewer.

---

## iterate to green
- fix the smallest thing the failing gate points at, then re-run that gate.
- after any change to timeouts, re-check the instruction suffix number still matches `[agent].timeout_sec`.
- run oracle a few times — reference verification on the harness runs it repeatedly and demands 1
  *every* time, so flush out nondeterminism now.
- when all four are green, run your `cheat/` attempt one more time and confirm it still scores 0.

## checklist
- [ ] anchor scan clean of errors; every declared tool shows `N` + `E` + `S`
- [ ] answered the stub test out loud — the anchor carries real weight
- [ ] oracle = 1 (repeatably)
- [ ] nop = 0
- [ ] `harbor check` blocking findings resolved
- [ ] cheat attempt still scores 0
- [ ] suffix number == `[agent].timeout_sec`
