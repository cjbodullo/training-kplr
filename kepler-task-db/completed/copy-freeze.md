# copy-freeze — Software / Data engineering — PASSED 2026-08-03

`lPRxxReRPSMar7WxpLk5`. All nine gates. **difficultyProbe 2 of 8 (in band),
easinessProbe 0 of 3, trajectoryReview pass.** Awaiting human review.

## What it is

Core problem, subject stripped: *decide which stored variant of a piece of
content is still usable at a release cut, and what a market takes when none is,
where usability turns on the history of the source and on sign-off and review
authority, and the shop's conventions are proved only by how the shipped
catalogue's consumers react.*

Subject: the localisation depot of a maker of self-service ticket kiosks. Nine
markets, three release trains, three channels (screen, printed ticket, spoken
prompt), base-market fallback (nl-BE←nl-NL, de-AT←de-DE, fr-BE←fr-FR). The agent
writes `/app/cut.json`: for each of 14 open cuts, per key in scope, a segment id
or `SOURCE` or `BLOCK`. 784 entries, exact match, all or nothing.

Localisation was untouched in the local corpus: translat / localis / locale /
glossary / terminolog all scored 0 hits across every task-src instruction.
Apparatus: XSLT ingest (0 prior uses), Object Pascal kiosk unit, warehouse
PL/SQL, a field service call log. None runnable in the container.

## The six graded readings

| reading | reference | ablation, of 784 |
|---|---|---|
| sign-off scope | the appointed distributor's hand covers every channel, anyone else covers only the channels named | 151 / 74 |
| source materiality | stale only if the english TEXT moved after the kit | 53 / 45 |
| finding severity | upheld MAJOR or CRITICAL withdraws, MINOR does not, dismissed never did | 18 / 62 / 89 |
| pack hold | a pack with a rejected unit is unusable entire; a stream loses only the rejected segment | 87 |
| inheritance | fare copy is never taken from a base market | 17 / 43 |
| nothing standing | legal copy is left out rather than shown in english | 35 / 189 |

Published as mechanics: the whole ingest, scope off the feature table, ranking
(newest kit, later return breaks ties), sign-off dating, that a finding takes
effect on its settled date and binds the market that raised it and any market
taking copy from there.

## The three rounds, which are the transferable part

| v | change | easiness | difficulty |
|---|---|---|---|
| 1 | k=6, service log annotated each symptom with its cause | **2/3 too_easy**, 807/858/915 s | — |
| 2 | medium rewrite + instruction trim + k=7 + unstated severity boundary | 1/3 pass, 799/1000/1273 s | **0/8 too_hard**, 1150-2094 s |
| 3 | undo the two extras, keep the medium rewrite | 0/3 pass, 810/841/923 s | **2/8 in band**, 1225-1879 s, $5.45-8.32 |

v1's leak was the field service log: every entry paired a symptom with the
depot's answer, and the answer named the cause. Rewritten to symptom plus what
the desk did, with identifiers kept and causal sentences cut, and a build scan
for the words that would give it away. That single lever moved the easiness
probe.

v2 stacked two more increments on top and skipped the band. The read that
stopped a redesign: an easiness agent had solved the identical v2 bundle at
799 s, so every reading was derivable and 0/8 was p^k. v3 undid exactly those
two — restored `WHERE severity IN ('MAJOR','CRITICAL')` on the re-order queue
(a view that FILTERS on a threshold states it; one that prints and sorts by it
does not) and published the market-reach rule in the handbook — with the graded
data untouched.

## Standing guards in the bundle

* `dev/rivals.py` — sweeps all 648 reading combinations: exactly one reproduces
  the sealed cut, nearest wrong is 17 entries out, and all 648 agree on the
  three trial cuts.
* `dev/evidence.py` — the exception report and the two kiosk faults a catalogue
  can trip, reimplemented from the register, must be empty under the reference
  across all 27 cuts and must fire under the reading they speak to; every
  service-report claim asserted true and asserted to move under its rival; no
  service report may name a graded cut.
* `dev/audit.py` — 33 citations, every reading in ≥2 files with ≥1 in code, a
  gloss scan over consumer comments, and a banned-word scan over the call log.
* `dev/ablate.py`, `dev/find_examples.py`.

## Cheats confirmed 0

The natural reading of all six conventions; the trial manifests played back
under the open cut ids; `SOURCE` everywhere; a self-written reward file with a
process left rewriting it.
