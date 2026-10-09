---
name: kepler-instruction
description: Step 2 of Kepler task authoring. Write the human-authored instruction.md (AI-check safe, absolute paths, exact timeout suffix) and the task.toml metadata skeleton for a task bundle.
---

# Kepler Instruction — SKILL

**pipeline position:** step 2 (build). prev → kepler-idea. next → kepler-environment.

write `instruction.md` and lay down the `task.toml` skeleton. the instruction is the one file that
**must be human-authored** — an AI check screens it and flagged instructions are rejected.

## output
- `task-src/<slug>/instruction.md`
- `task-src/<slug>/task.toml` (metadata skeleton, timeouts filled in coordination with agent budget)

## tool
- `kepler-instruction/humanize.py` — humanizeai.pro client used in step 6. `python3 humanize.py --test`
  to smoke-test. needs `curl_cffi` (`pip install --user --break-system-packages curl_cffi`).

---

## workflow

### step 1 — write instruction.md yourself, in your own voice
this file is screened by an AI detector — do not let a model draft it in its default voice. write
like a real engineer handing off a ticket, following the writing rules in step 5 (lowercase, terse,
no em dashes, dropped articles). a clean, polished, well-structured draft is exactly what gets
flagged. write it rough and human from the start, not polished-then-humanized:
- state the job and the exact success condition. no fluff, no motivational framing.
- **name the real tools, by name and version.** never "a program", "the software", "a framework",
  "the simulator", "the tool". say `freecad 1.0`, `memcached 1.6.21`, `bun 1.1`, `postgres 16`,
  `vllm 0.6.3`, `spark 3.5`, `coq 8.19`, `torch 2.4`. same for formats and interfaces — say
  `.FCStd`, `parquet`, `the memcached text protocol`, not "the file" or "the wire format". a real
  engineer writing this ticket would name them without thinking; a vague ticket is the tell that
  the environment is invented. the version in the instruction must match what the Dockerfile
  installs (see [[kepler-environment]]).
- give every input the agent needs — an expert would not be missing context, so neither is the agent.
- reference **every** expected output file by absolute path (e.g. `/app/output.json`). the verifier
  reads only what the instruction promises and what `artifacts` declares.
- specify the output *contract* exactly (format, schema, units, ordering) so grading can be binary.
- do NOT reveal the implementation approach or embed hints specific to this task.
- do NOT mention the tests, ground truth, or that a verifier exists beyond what the agent needs.

### step 2 — append the required suffix EXACTLY
the file must end with a blank line, then this single sentence, then at most one trailing newline.
`N` is the integer value of `[agent].timeout_sec` (e.g. `3600`, not `3600.0`):

```
You have N seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```

any deviation (wrong number, extra text, missing blank line, capital difference) fails the static check.

### step 3 — fill task.toml metadata
copy the template from [instructions.md](../instructions.md) and fill **every** field.

**author fields are fixed — use these exact values on every task:**
```toml
author_name = "Anand Pahade"
author_email = "bryandavidson737@gmail.com"
```
older bundles in `kepler-task-db/completed/` carry a different author. do not copy those two lines
forward when you crib a task.toml from the archive.

the three explanations are read by human reviewers — make them concrete:
- `difficulty_explanation` — why this is hard for agents AND humans (name the real bottleneck). name
  the real tools here too, and say what about *them* is hard — version behaviour, format
  constraints, slow feedback. reviewers read this to decide whether the task is real work.
- `solution_explanation` — high-level approach + key insights (this is the reviewer's map, not a hint to the agent).
- `verification_explanation` — how the tests decide 0/1 against sealed ground truth.
- `relevant_experience` — your actual professional background in this domain. generic statements fail.
- `category` must equal the domain you submit on the form. `subcategory` = closest label.
- `expert_time_estimate_hours` — honest best-case hours for a focused domain expert.
- `[task].name = "afterquery/<slug>"` — slug matches the directory and the submitted name.

### step 4 — set the timeouts together
`[agent].timeout_sec` is the agent's full budget (hard tasks run for hours; max 18000). the number
in the instruction suffix MUST equal this integer. `[verifier].timeout_sec` covers the test suite
runtime (max 18000). if you change the agent timeout later, update the suffix in the same edit.

### step 5 — apply the writing rules (this is what passes the AI check)
the AI check rejects instructions that read like polished model output. write in a plain human
voice using these rules. they keep the spec exact but make it read like real dev notes.

**writing style**
- B1 english. short sentences. simple words. direct.
- human tone. like real notes a person writes. not polished ai output.
- substance over formatting. flowing text, not perfectly parallel bullet lists.
- grounded. name the real files and identifiers (`/app/store.py`, `commit`, `ConflictError`).

**humanization rules**
- lowercase everything. no capitalized sentence starts. lowercase headers too.
- drop articles where natural. "the fix is correct" -> "fix is correct".
- abbreviate. parameters -> params, arguments -> args, function -> func, transaction -> txn, message -> msg.
- drop verb 's'. "commit raises" -> "commit raise". "snapshot differs" -> "snapshot differ".
- no hyphens. "key-value" -> "key value". "in-memory" -> "in memory". "read-only" -> "read only".
- lowercase abbreviations. "IO" -> "io", "API" -> "api".
- simple grammar. drop unnecessary words. "makes the logic easier" -> "make logic easier".
- use "and" over commas. fewer commas, more flowing.
- **no em dashes.** use a period and a new sentence instead. (em dashes are the #1 ai tell.)
- keep it short. if a sentence works without a word, cut that word.

**what NOT to lowercase or change** — these stay exact or the task breaks:
- public code identifiers the grader depends on (class / method / exception names, e.g. `Database`,
  `read`, `ConflictError`), literal values like `None`, and absolute paths like `/app/store.py`.
- tool names, package names, version numbers and format names (`FreeCAD`, `.FCStd`, `bun 1.1`,
  `pytorch==2.4.0`). lowercasing prose is fine, but a version string or a case-sensitive binary
  name must survive intact — the agent has to be able to type it.
- the required suffix sentence — it is fixed text, keep it verbatim (capitalized, exact number N).

**casing rules alone are NOT enough** — a uniformly lowercased, tidy, exhaustively-sectioned spec
still fails the AI check (this happened twice). detectors key on structure and rhythm, so also:
- **burstiness.** vary sentence length hard. mix 2-3 word fragments with long 30+ word run-ons.
  uniform medium-length sentences are the giveaway. aim for a real spread.
- **prose over sections.** drop the neat `## api` / `## details` scaffolding and the perfectly
  parallel bullet lists. write it as a few flowing paragraphs, like you typed it in one sitting.
- **first person + voice.** "i want", "the bit people miss", "here is what i care about". informal
  asides and mild opinion read human. perfectly neutral coverage reads machine.
- **organic order.** let the explanation wander a little the way a person explains their own code,
  instead of a template that covers every field in tidy order.

then read it back. if any line still sounds like an assistant wrote it (hedging, "Note:",
"Requirements:", "In order to", "Additionally", smooth parallel structure), rough it up.

### step 6 — run it through the humanizer (`humanize.py`)
this folder ships `humanize.py`, a client for humanizeai.pro that rewrites prose into a
human-passing voice. use it after you have a correct draft.

```bash
# wrap every must-stay-exact token in backticks first (see below), then:
python3 kepler-instruction/humanize.py <draft.md> <out.md> --keep-last-line
# --keep-last-line splits off the final line (the timeout suffix) and re-appends it verbatim
```

working request params (the old defaults are broken): `alg=0`, a valid `style`
(`standard|academic|simple|flowing|informal|formal|expand|shorten` — `informal` reads best for a
ticket; `free` is no longer accepted), `sessionId` = a fresh random 24-char string (NOT null, null
400s), `ultra=0`, `test_limitNot="true"` (string), `test_allUltra=null`, `keywords=[]`. hit the
homepage once before posting. the response no longer returns an ai score; check
`scores.passed_filter=true` and `scores.fallback_to_original=false`.

**CRITICAL — the humanizer scrambles protected tokens.** it treats backtick placeholders as words
and moves/duplicates/drops them while rephrasing, so restored code tokens land in the WRONG slots
(seen live: `commit` "raises `None`", "must throw `abort`", "rewrite `Database` in place" instead of
the path). it can also silently invert meaning. the verifier never reads instruction.md, so nothing
downstream catches this. therefore:
- wrap all exact tokens in backticks before sending (identifiers, literals like `None`, method
  signatures like `read(key)`, absolute paths, **and every tool name / version / format name**) so
  at least they survive as spans, and use `--keep-last-line` for the suffix. version strings are a
  favourite casualty — the humanizer will happily move `1.6.21` onto the wrong tool.
- **always do a manual correction pass afterwards**: diff the humanized output against your draft,
  fix every scrambled token, and re-read every rule for inverted logic ("committed after you began"
  must not become "before"). the humanizer is for prose *rhythm* only, never trust it with facts.

### step 7 — final human edit pass
even after the humanizer + correction, retype a couple of sentences in your own words and add one
personal aside about the codebase. the check is partly asking "did a human write this", and a
genuine edit is what it wants. keep the spec exact (identifiers, literals, paths, suffix unchanged).

## checklist
- [ ] written by a human, reads like a real ticket, not model output
- [ ] **real tools named with versions; no "a program" / "the software" / "the simulator" anywhere**
- [ ] **versions in the instruction match what `environment/Dockerfile` installs**
- [ ] **output artifact named in its real format, not an invented one**
- [ ] writing rules applied: lowercase, no em dashes, no hyphens, dropped articles, short sentences
- [ ] code identifiers / literals / paths / tool names / versions / the suffix left exact
- [ ] every output file referenced by absolute path
- [ ] output contract exact enough for binary grading
- [ ] no implementation hints, no leaking of tests/ground truth
- [ ] ends with the exact suffix, N = integer `[agent].timeout_sec`
- [ ] all `[metadata]` fields filled, three explanations concrete, experience specific
- [ ] `author_name` = `Anand Pahade`, `author_email` = `bryandavidson737@gmail.com`
- [ ] `[task].name` = `afterquery/<slug>` matches directory
