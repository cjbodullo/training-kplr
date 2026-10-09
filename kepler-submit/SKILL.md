---
name: kepler-submit
description: Final step of Kepler task authoring. Run the pre-submit checklist, zip the bundle contents, fill the submission page (idea check, category and labels, task name), and record the task to kepler-task-db.
---

# Kepler Submit — SKILL

**pipeline position:** final step (ship). prev → kepler-validate. records to kepler-task-db/.

final checklist, zip, submit, and record. only reach here once all three local gates are green.

---

## two ways to submit
- **automated (preferred): [[kepler-api]]** — drive submit + live status polling + delete/rebuild/
  resubmit from the CLI. after the checklist below is green:
  ```bash
  python3 kepler-tools/kepler_run.py loop \
    --zip tasks/<slug>/<slug>.zip --name <slug> --category <Cat> --labels a,b \
    --src task-src/<slug>
  ```
  needs the token bridge running (pm2 token server + extension). a single shot is
  `kepler_run.py submit ...`; `watch <submissionId>` polls; `kepler_api.py delete <id>` removes a
  failed one.
- **manual (fallback): the web submission page** — same fields, described below.

either way, run the pre-submit checklist first.

## pre-submit checklist

### files present and correct
- [ ] `instruction.md`, `task.toml`, `environment/Dockerfile`, `solution/solve.sh`,
      `tests/test.sh`, `tests/Dockerfile` all exist (hard-required by the pipeline)
- [ ] `instruction.md` ends with exact suffix, N == `[agent].timeout_sec` (integer)
- [ ] `[task].name = afterquery/<slug>`, slug matches directory and the name you'll submit
- [ ] all `[metadata]` fields filled; three explanations concrete; `relevant_experience` specific
- [ ] `author_name = "Shaswat Panda"`, `author_email = "pandashaswat712@gmail.com"` (not copied
      over from an archived bundle)
- [ ] `category` matches the domain you pick on the form; `subcategory` = closest label

### real-tool anchoring
- [ ] `instruction.md` names the real tools with versions — no "a program" / "the software"
- [ ] those tools are installed in `environment/` at the stated versions, from upstream
- [ ] `solution/solve.sh` actually invokes them; the artifact is in a real format
- [ ] `python3 kepler-tools/anchor_check.py task-src/<slug> --tools <...>` shows no errors
- [ ] the stub test answered: swapping the tool for a stub WOULD change the difficulty

### contract + isolation
- [ ] verifier writes `/logs/verifier/reward.txt` (0/1) on every path + CTRF report
- [ ] `[verifier] environment_mode = "separate"`; tests baked with `COPY . /tests/`
- [ ] nothing in `environment/` references `solution/` or `tests/`
- [ ] `artifacts = [...]` above the first `[section]`, exact absolute paths
- [ ] pip pinned `==` in all four scanned files; apt unpinned + cleaned
- [ ] no `allow_internet`; no `FROM --platform=`; timeouts ≤ 18000
- [ ] `cpus` ∈ {1,2,4,8,16}, `memory_mb` ∈ {1024,2048,4096,8192,16384}, `storage_mb` ≤ 40960
- [ ] `gpus = 0`, or `gpus = 1` + exactly one `gpu_types` class (ML + GPU option only, no compose)
- [ ] compose (if any) declares **no volumes at all** — named and bind both fail now
- [ ] no `harbor-canary` marker anywhere in the bundle
- [ ] not a re-skin of one of our own tasks, and it breaks agents differently than the last few

### proof
- [ ] oracle = 1, nop = 0, `harbor check` clean (from kepler-validate)
- [ ] cheat/ attempt scores 0

---

## the submission page (fill in this exact order)
prepare a `SUBMISSION.md` in the task dir capturing each field, so the human can paste without
guessing:

1. **Phase-1 idea check (optional, advisory).** one or two sentences (≤ 8000 chars) describing the
   task the way the acceptance rubric reads it — the hard thing, what "done" is, and why a naive
   solution fails. never affects the submission; it just catches dead-ends. mirror the page's own
   example: a concrete setup + an exact, verifiable success condition. **name the real tools in
   this pitch** — a reviewer reading "an agent tunes a scheduler" cannot tell real work from a
   simulation, and that read is the one that decides.
2. **Category & labels.** pick exactly one **category** (must equal `[metadata].category`) and
   **one or two labels** (subdomains) — the spec cut this down from a wider pick. set
   `[metadata].subcategory` to the primary label.
3. **Task name.** the slug only (e.g. `mvcc-snapshot-isolation`) — must match
   `[task] name = "afterquery/<slug>"`, at most 3 hyphen-separated words.
4. **Bundle zip.** build the deliverable from the source dir — `bundle.py` zips the **contents** of
   `task-src/<slug>/` (no wrapping folder) into `tasks/<slug>/<slug>.zip`, excluding non-bundle files
   (`SUBMISSION.md`, `required_tokens.txt`, `*.zip`, `__pycache__`, `*.pyc`):
   ```bash
   python3 kepler-tools/bundle.py task-src/<slug> tasks/<slug>/<slug>.zip
   ```
   re-run after any edit to the source. (the automated loop does this for you.)
5. **Submit for validation** kicks off the automated pipeline; watch every stage live on the task
   page: structural → AI check → similarity → reference verification → quality review → anti-cheat
   probe → difficulty probe (8 attempts, **1–7 band**) → run audit → human review. the spec's stage
   list no longer shows a separate easiness pre-screen; assume it is folded in until a submission
   says otherwise.

the page restates the required layout as its own checklist (task.toml name + full metadata +
separate verifier + timeouts ≤ 18000 + no allow_internet; instruction ends with the timeout suffix;
env Dockerfile cleans apt cache with no apt version pins and never references solution/ or tests/;
tests write reward.txt 0/1 + CTRF; tests Dockerfile bakes COPY . /tests/, pins pytest==9.1.1 +
pytest-json-ctrf==0.5.2, mkdir -p each artifact parent). the pre-submit checklist above already
covers all of it — treat the page's list as the final cross-check.

## after submit — record it
run `kepler-task-db` updates:
- add slug + conversation/task id to `kepler-task-db/submitted.md` with domain + status.
- copy the final `task.toml` + `instruction.md` (or the whole bundle manifest) to
  `kepler-task-db/completed/<slug>.md` for the archive.
- mark the idea in `kepler-task-db/ideas.md` as `submitted`.

## if the pipeline rejects it
rejections always include a written reason. the [[kepler-api]] loop reads the failed stage and runs
the matching rebuild hook automatically (ai_check → humanize+correct; other stages → your
`--rebuild-cmd`), then deletes the failed task and resubmits. map it back to a skill and iterate:
- AI-check flag → kepler-instruction (rewrite in human voice).
- similarity → kepler-idea (idea overlaps existing task; pick a fresher angle). note the fix is a
  fresher *problem*, not an invented tool — see kepler-idea step 1b.
- quality review or human review calling it synthetic / not real work → kepler-idea step 1b. this
  is an anchoring failure and it is not repairable in the bundle: re-aim the task at a real tool.
- oracle≠1 / nop≠0 → kepler-solution / kepler-verifier / kepler-validate.
- anti-cheat pass → kepler-verifier (harden grading).
- difficulty out of band → kepler-idea (too easy: raise difficulty; unsolvable: fix spec/solvability).
- run audit → kepler-instruction / kepler-verifier (spec ambiguity or grader exploit).
