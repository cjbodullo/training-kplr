# cohort-commit — ML / Training — PASSED ALL NINE GATES

`afPo453XvGcvo4Fm6O8x`, 2026-08-03, Needs Review.
easinessProbe **1/3**, difficultyProbe **1/8 in band**, trajectoryReview pass.

## Core problem (subject stripped)

State the exact integers each committed round of a threshold-recovery
aggregation protocol contains — who was seated, who it took an update from,
the denominator, the committed coordinates — where the protocol ships whole
and what each timing / recovery / abort event OBLIGES is proved only by
programs that consume the ledger.

Subject: a distributor's federated training service for an on-meter load
disaggregation model. Beat: privacy-by-design meant nobody ever kept the round
ledger, and the model-risk review needs it. Deliverable is DATA at
`/app/ledger.json`; the verifier `json.load`s it and runs no agent code.

## The measurement that matters

Four builds, one bundle, one variable at a time:

| build | k | evidence estate | easiness | trial durations |
|---|---|---|---|---|
| v1 | 7 | 3 programs, ~450 lines, rules narrated in comments | 3/3 | 348-379s |
| v2 | 7 | same, every rule-stating comment stripped | 3/3 | 365-501s |
| v3 | 13 | same | 2/3 | 502-575s |
| v4 | 15 | **7 programs, ~1010 lines, branches unsignposted** | **1/3** | 899-1379s |

**The evidence surface was the lever, not k.** 13→15 readings cannot explain
the jump — `0.969^15 ≈ 0.62` predicts another easiness failure. What changed is
that the conventions stopped being findable in three short files. Every earlier
probe finished inside 4% of its clock, which was the standing signal that
*search* cost nothing and only *resolution* remained.

## Reusable

* [[a-comment-that-states-the-rule-is-prose]] — a comment stating the rule is
  prose wherever it sits, worth ~1 point of p.
* Consumers must contain the rules to be fair, so p floors near 0.95-0.97;
  once there, spread them thin rather than adding more.
* Conditional refinements are legitimate k, but an ablate-against-the-naive-base
  check calls them dead. Use: moves ≥3 rounds from the TRUE base, plus all
  single-flip ledgers pairwise distinct, plus an explicit nesting report.
* Drop a reading that ablates at 0 for a structural reason (`seated_donor`).
* Masked values + key material is a smallness oracle — see
  [[masked-aggregation-is-a-smallness-oracle]].
* After adding a reading, verify the trigger events exist in the generated data
  before trusting the ablation count; two generator patches silently no-op'd.
