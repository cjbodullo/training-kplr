---
name: kepler-idea
description: Step 1 of Kepler task authoring. Pitch a task idea and score it against the acceptance rubric (difficulty, verifiability, specificity), pick the domain and payout tier, name the verifier shape, and log it. Use before building any bundle.
---

# Kepler Idea — SKILL

**pipeline position:** step 1 (plan). runs before any files are built. next → kepler-instruction.

pitch a task idea, score it against the acceptance rubric, confirm domain + payout tier, and log
it. cheap to run — kill weak ideas here before hours go into a bundle.

## output
- log every scored idea to `kepler-task-db/ideas.md` (status: candidate / building / dropped / submitted)

---

## workflow

### step 1 — draft the idea in one paragraph
what is the real-world job, what does "done" look like, why would a person be paid for it.
name the single domain (Science / Software / ML / Operations / Security / Hardware / Media) and
the payout tier ($300 for Science·Software·ML, $200 otherwise).

**name the real tools in this same paragraph.** the pitch is not an idea until you can say which
actual software the job runs on — FreeCAD, memcached, bun, MySQL→Postgres, vLLM, Next.js, React,
Coq/Lean, Spark, UEFI, PyTorch, whatever the practitioner would really open. "an agent tunes a
scheduler" is not an idea. "an agent tunes Spark 3.5 shuffle partitioning against a real parquet
dataset" is. see step 1b — this is a screen, not decoration.

### step 1b — the real-tool anchor screen (added 2026-08-13; now LOCAL policy)

the spec dropped its anchoring section, so nothing upstream enforces this any more. keep the
screen anyway: anchored tasks read as real work to the quality reviewer, and real tools supply the
version behaviour and error surfaces the verifier grades. it is our bar, not theirs.

we represent **real computer work**. a task that runs entirely inside a world we invented is not
that, however hard it is. so before scoring, answer these four in writing:

1. **which real tools does this task genuinely depend on?** name them with versions. they must be
   things that exist outside this bundle and that someone uses at work: real binaries and their
   real flags, real file/wire formats (`.FCStd`, ELF, parquet, protobuf, the memcached text
   protocol), real build systems, real APIs and their real error surfaces, real upstream version
   behaviour. one is enough if the task truly rides on it; zero means the idea is not ready.
2. **would removing the tool leave the task intact?** if you could swap the named tool for a
   200-line stub in `environment/` and nothing about the difficulty changes, the tool is set
   dressing. the anchor has to carry weight — its real semantics, quirks, formats or failure modes
   are part of what makes the work hard.
3. **is the agent fighting the tool or fighting my invention?** reverse-engineering a simulator we
   wrote is not real work, and it collides with the artificial-difficulty ban. the agent should be
   fighting something a practitioner also fights.
4. **can i say the sentence?** "a `<role>` doing this at work would open `<tool>` and produce
   `<real artifact>`." if that sentence needs hedging, the idea is still abstract.

**how this squares with screen 4 ("bespoke system is the fix").** those two rules point in opposite
directions until you split them: the **toolchain is real, the problem on top of it is bespoke.**
protocol-clone's 23 decisions still exist nowhere — that is fine and still the goal — but the thing
they should be decisions *about* is a real protocol, real engine, real format. put novelty in the
workload, the constraints, the data, the failure being chased. never in an invented tool. if you
find yourself writing a simulator because no real tool fits, that is the signal the idea is aimed
at a world instead of a job — redesign around the closest real tool and move the hard part on top
of it.

also worth knowing: anchoring usually *helps* the difficulty band. real tools bring real version
quirks, real undocumented behaviour, real slow feedback loops — difficulty you can explain, and
difficulty an agent cannot shortcut by reading our own source.

### step 2 — score against the 3 rubric axes
rate each low / med / high. an idea needs high on all three to be worth building.

you can also run the **real reviewer** (same rubric a human uses) via the API — advisory, never
affects the submission. see [[kepler-api]]:
```bash
python3 kepler-tools/kepler_run.py idea "<one-sentence pitch>"
```
it returns a decision (Accept / …) plus a written review. treat a non-Accept as a redesign signal
before you build. still do the manual scoring below — the API call is a cross-check, not a
replacement.

- **difficulty** — an expert takes hours to days across multiple sessions; a frontier agent fails
  for a *real* reason. must land in the **1–7 / 8** solve band (the spec widened it from 1–5; the
  probe telemetry in [[kepler-task-db]] had already shown in_band at 6/8). only 0/8 and 8/8 fail,
  so the binding edge is **too hard**, not too easy — never trim a design to dodge a 6. if you can
  picture an agent one-shotting it, it's still too easy.
- **verifiability** — outcome is binary and machine-checkable: a program can decide 0 or 1 with no
  human judgement. if grading needs taste or fuzzy matching, redesign until it doesn't.
- **specificity** — the instruction can fully pin down what "done" means with absolute paths and
  exact output contracts, no ambiguity an expert would have to guess at.

### step 3 — sanity-check the traps
reject / rework the idea if any of these are true:

- solution (or a near-twin) is findable online — obscurity is not difficulty, agents will search.
- difficulty comes from trivia, memorization, tokenizer/obfuscation tricks, or withholding info an
  expert would obviously have.
- it's task-hunting against today's models (a shallow gap that vanishes next release) rather than
  difficulty you can *explain*.
- verification would need partial credit or human judgement.
- it overlaps an existing public Frontier Bench task or another submission (similarity check).
- **it re-skins our own back catalogue.** the similarity gate now compares against our earlier
  tasks too, and "new subject matter over the same scaffold, same reference-solution shape, same
  verifier shape" is a rebuild — rejected however thoroughly the surface changed. the deeper we
  are into a pattern, the further the next idea has to sit from it.
- **it breaks the agent the same way as the last few tasks.** name the failure mode before
  building (a race it cannot see, an invariant it will not preserve, a rule it must infer rather
  than read) and check it against the recent entries in [[kepler-task-db]]. the spec names our
  exact habit: a pile of tasks that all reduce to reconstructing the numbers a missing tool would
  have produced counts for about one, whether it is set in DNS caching, freight tariffs or gene
  networks.
- **it names no real tool, or the environment is a world we invented end to end** (step 1b). a
  simulator we wrote standing in for a real toolchain, or artifacts in a file format that exists
  only in this bundle, is a rework signal even when everything else scores high.

### step 3b — the four screens (added 2026-07-28, from ~14 easiness rejections)

every idea killed so far died on one of these. check them BEFORE step 4, on paper first and
then with a cheap spike. cost of a spike is one file; cost of skipping it is a bundle plus a
pipeline round trip.

1. **is it hard WITH a correctness oracle?** agents self-check constantly. rule-induction shipped
   6000 training pairs and was solved 3/3 in ~800s because the corpus was a free unlimited oracle.
   reactive-spreadsheet and remat-schedule both let the agent verify correctness and still landed
   in band, because the binding constraint was an INVISIBLE bar and the engineering was genuinely
   hard. assume the agent will have an oracle for anything locally checkable, then ask what is left.
2. **static corpus = free oracle (structural).** with exact-match grading over shipped data, every
   decision either changes a corpus output (so run/diff/fix converges for free) or it does not (so
   it is undetermined and unfair). there is no middle ground. if the design says "the data covers
   the primitives but not their conjunctions", it is already dead — see `trace-inference`. what
   works instead is METERING the oracle (protocol-clone) or grading on genuine off-support
   extrapolation with a parametric model (reaction-mechanism, echelle-selfcal, telemetry-codec).
3. **prefer BINARY failure over a continuous quality metric.** this is the big one, and it is worth
   more than the rest put together. every task that landed in band fails the agent *discretely*:
   protocol-clone byte-exact over 100 sessions, reactive-spreadsheet exact cell values under a work
   budget, remat-schedule legality at budgets on the feasibility floor. every task graded on a
   continuous quality metric died, because a competent partial solution always lands within
   1.1-2x of the reference and no bar fits in that space: lens-design, cnot-synth, spin-ground-states,
   xor-circuit, observing-queue, compaction-plan, snapshot-gc, frustrated-cluster, and locally
   regalloc-floor (effort closed 93.2% of the gap), stream-bound (last insight worth 1.8x, saturating)
   and bundle-cache (the reference LOST to plain LRU at 0.67x).
   if you are grading "how good is it", stop and redesign until you are grading "is it right".
   when a continuous metric is unavoidable, the best competent standard approach must sit at >= 3x
   the reference, and you must SWEEP the parameter that should widen the gap — stream-bound's
   saturated instead of widening, which is the tell. never repair a weak gap by tuning the cost
   model backwards from the answer you want; that is artificial difficulty and the quality gate reads it.
3b. **scaffolding is not difficulty, and it will masquerade as it.** if solving means first
   rebuilding a simulator, harness or tool from your spec, that rebuild is most of the clock and
   none of the insight — and withholding it is exactly the "artificial difficulty" the spec bans.
   SHIP the scaffolding, then measure what is left. causal-probe measured this cleanly as a single
   variable: with no practice simulator, 2 of 3 agents timed out at 14400s and the one that
   finished took 12385s and $22.76; shipping one dropped it to 1253-2388s and $1.70-3.06. **10x on
   both time and cost.** the real problem was 25 minutes. a task that looks hard because the agent
   is busy is not hard, and the easiness probe will find that out for you at the cost of a
   submission.

3c. **for a meter to bite, an efficiency gap must exist — measure it first.** budget-limiting only
   creates difficulty when the best strategy is much leaner than the obvious one, so the budget can
   sit between them. protocol-clone had that (610-frame designed plan vs a blind grind that never
   converges) and landed 4/8. causal-probe did not: over 38 systems the obvious strategy scored
   12/24/32/33 at budgets 12k/16k/22k/32k while the cleverer observational-pruning version scored
   11/20/25/33 — **worse, not better**. the obvious strategy WAS the efficient frontier, so no
   budget separated good from obvious without also killing the oracle. measure the gap before
   building, not after three submissions.

4. **is the far side textbook or findable online?** the spec forbids findable solutions outright.
   regalloc-floor's reference advantage was live-range splitting + rematerialisation, which is what
   LLVM's greedy allocator does in readable source. deadtime-recovery (paralyzable dead time,
   Knoll ch4) and atomicity-retrofit (canonical lock order + validate-retry) died the same way.
   "bespoke system" is the fix: protocol-clone's 23 decisions exist nowhere. **read that together
   with step 1b** — bespoke means the *problem*, not the *toolchain*. real tools, novel problem on
   top. inventing the tool to dodge findability trades one rejection for another.

if an idea passes all four, it is worth a spike. if it fails any, kill it here and log why.

### step 4 — pick a proven source of difficulty
strong ideas usually get hardness from one of:
- long-horizon work with many dependent steps.
- rich environment the agent must explore (microservices, filesystems, databases).
- dynamic environment (live traffic, multi-container).
- cross-domain expertise in several areas at once.
- iterative trial-and-error problems (not read-and-solve).
- **depth in a real tool** — its actual semantics, version quirks, format constraints, error
  surfaces and slow feedback loops. this is the anchored source of difficulty and the one that
  ages best: it cannot be shortcut by reading our source, because the source is upstream's.

### step 5 — name the verifier shape early
before building, state in one sentence *how* a program will grade it: what artifact the agent
produces (absolute path), and what the verifier checks against sealed ground truth. if you cannot
name this cleanly, the idea is not verifiable enough yet — loop back to step 2.

prefer an artifact in a **real format** the named tool actually reads or writes — a `.FCStd` file,
a parquet dataset, a protobuf message, an ELF binary, a real config the tool will parse. grading a
real format is more convincing to reviewers than grading a json blob we made up, and it keeps the
verifier honest: the tool itself becomes part of the check.

### step 6 — log it
append to `kepler-task-db/ideas.md`: slug, domain, tier, the 3 axis scores, the one-sentence
verifier shape, and status. pick a slug now (lowercase, ≤ 3 hyphen-separated words) — you build in
`task-src/<slug>/` (editable source), ship `tasks/<slug>/<slug>.zip` (deliverable), and set
`[task].name = afterquery/<slug>`.

start the verifier-shape cell with the anchor so it is greppable later and the similarity/rework
history stays readable:
```
anchor: FreeCAD 1.0 + .FCStd | verifier compares /app/out.FCStd geometry against sealed ground truth ...
```

## definition of ready (all true before moving on)
- [ ] high on difficulty, verifiability, specificity
- [ ] single domain + payout tier chosen
- [ ] **real tools named with versions; step 1b's four questions answered in writing**
- [ ] **difficulty survives the "swap the tool for a stub" test — the anchor carries weight**
- [ ] verifier shape stated in one sentence, ideally over a real file format
- [ ] solution not findable online, no overlap with existing tasks
- [ ] slug chosen and logged in ideas.md, verifier-shape cell prefixed with `anchor:`
