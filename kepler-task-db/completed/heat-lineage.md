# heat-lineage (Software / Data engineering)

Submitted 2026-08-01, `zHcscBinfgqH5pTRiJpR`. **ALL NINE GATES PASSED on v6.**
`difficultyProbe` **3 of 8**, dead centre of the 1-6 band; `easinessProbe` 1 of 3
against a cap of 1; `cheatProbe`, `qualityCheck` and `trajectoryReview` all green.

## What it is

Exact fractional provenance through a secondary-aluminium melt shop. The agent
leaves `/app/feed.json` giving, for each of 14 shifts and 305 ingot bundles, the
share of every purchased lot in that bundle as a reduced rational. All or
nothing across all 305.

Core problem, subject stripped: *compute exact fractional provenance through a
chain of destructive batch operations, where the conventions deciding whose
mass is lost, buffered or returned exist only in the branches of the systems
that consume the genealogy.* Mass balance closes under every reading, so
conservation is a free non-oracle.

## The six rounds, and what each one measured

| v | verdict | what it taught |
|---|---|---|
| 1 | cheatProbe, reward 0 | a practice answer co-located with its input is a foothold |
| 2 | cheatProbe, reward 0 | a shipped checker that imports the submission beside answers invites heap theft |
| 3 | cheatProbe, reward 0 | a *lossy* rendering is still an answer; inverse-truncation beat it |
| 4 | easinessProbe 3/3 | consumers that MODEL the rule are a spec: 11 readings transcribed in 6-9 min |
| 5 | difficultyProbe 0/8 | removing the modelling removed the determinacy for 2 of the 11 |
| 6 | **passed** | 8 withheld readings, evidence that reacts or states a plant fact |

## The three settled findings

1. **Data artifact defeats the cheat probe.** Deliverable is data the verifier
   only reads; no agent code is executed, imported or evaluated in the grader,
   and no answer of any kind ships. Three vector patches failed; changing the
   contract passed first try.
2. **The medium is worth the whole band.** Same k, same data, only the
   consumers changed: modelling the attribution = 3/3 too_easy; reacting to a
   feed or stating a plant fact = 0/3.
3. **Citation count is not a determinacy test.** The audit was green while two
   readings were under-determined; the trials named them out loud.

## Calibration

**k=8 inferential readings over a 305-row all-or-nothing artifact = 3 of 8.**
Matches route-book (k=8 code-proved = 3/8) exactly. The bracket measured on
this one task: k=11 modelled 3/3 too_easy, k=11 inferred 0/8 too_hard, k=8
inferred 3/8 in band.
