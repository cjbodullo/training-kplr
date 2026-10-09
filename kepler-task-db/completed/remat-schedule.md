# remat-schedule (ML / Training) — submitted 2026-07-27 as lZDLEwsOmZXrla0kobqH

## instruction.md
```markdown
i need schedules for the graphs in `/app/instances`. there are 24. write all of them into `/app/schedules.json`.

what a schedule is, and what makes one legal, is written out in `/app/SPEC.md`. read that first. the short version is that a value has to be computed before anything reads it, computing it needs its inputs sitting in memory right then, memory is capped, and if you drop something and want it back later you compute it again and pay for it again.

legal is the easy half. you can get a legal schedule by rebuilding everything from scratch every time you need it, and that costs somewhere between three and six times what i am after. the job is to make the total compute cost small.

every instance has a cost bar. i am not telling you the numbers. i know each one is reachable because i have a schedule that reaches it. you need to be at or under the bar on all 24 of them. a single instance over and the whole thing fails, there is no partial credit here.

`/app/validate.py` will replay your file and say which schedules are legal and what each one cost. run it with `python3 /app/validate.py /app/schedules.json`. it checks legality and nothing else. it has no idea whether a cost is good, so do not read a clean run as being done.

format is at the bottom of the spec. keys are instance ids, exactly the string in the `id` field of each instance. values are the op lists. only `/app/schedules.json` is collected when i grade, nothing else you leave lying around matters.

no packages needed for any of this, plain python is enough. graphs run from 32 to 84 nodes.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```

## task.toml
```toml
artifacts = ["/app/schedules.json"]

[task]
name = "afterquery/remat-schedule"

[metadata]
author_name = "Sayan Banerjee"
author_email = "sayanbanerjee.writodesk@gmail.com"
difficulty_explanation = """
This is a search problem, not an implementation problem: the execution rules fit on one page and
writing a legal schedule is easy, but a legal schedule produced the obvious way costs three to six
times the bar. Nothing is transcribable, because knowing the rules tells you nothing about which
activations to keep. The instances are 32 to 84 nodes, so the resident-set state space is 2^32 to
2^84 and exhaustive search over it is hopeless; the agent has to find structure instead. The bar is
tight on purpose: the best uniform checkpointing strategy, taken over every possible spacing, still
lands 13 to 41 percent above it, so the natural first idea is not enough and neither is a small
improvement on it. Getting there needs several things at once — recomputing only the ancestors
actually missing rather than restarting from a fixed point, keeping what a recomputation passed
through so the reverse walk consumes it instead of rebuilding it, an eviction rule that accounts for
the fact that the value needed furthest in the future is also the most expensive one to reconstruct,
and a search over which values are pinned against that rule. Reward is binary over all 24 instances,
so a strategy that is excellent on the loose budgets and mediocre on the tight ones scores zero. The
memory budgets are deliberately near the feasibility floor, which is where the gap between a decent
heuristic and a real solver is widest.
"""
solution_explanation = """
Recompute on demand: to get a value back, compute exactly the ancestors that are missing, in index
order, and let everything that recomputation passes through stay resident, so the reverse traversal
consumes the segment for free rather than rebuilding it per step. When memory runs short, the
activation whose next use is furthest away is the lowest indexed one, because consumption runs
downwards; evicting it is locally right and globally wrong, since it is also the one whose
recomputation costs the most to redo. The reference resolves that tension with a pinned set that
overrides the eviction rule, chosen by a deterministic local search over single add, single drop and
swap moves, seeded from three starting sets. Every candidate pinned set is scored by constructing
its schedule and replaying it under the real rules, so infeasible choices are rejected outright and
the number being compared is the true cost. On every instance small enough to certify by exhaustive
search this finds the true optimum (23 of 24 certified instances exactly, worst case 1.2 percent
over), and it runs in under a second at 80 nodes. The shipped targets are exactly what it achieves.
"""
verification_explanation = """
The artifact is data, not code, so the verifier never imports or executes anything the agent wrote:
it replays each schedule under the same rules the spec states. Grading uses the verifier's own
sealed copy of the instances, so editing the copies under /app cannot soften a budget or a graph.
For each of the 24 instances the schedule must replay legally — every compute has its inputs
resident, nothing is computed while already resident, nothing is freed while absent, the resident
total never exceeds the budget, and the target node is resident at the end — and its total compute
cost must be at or under a sealed per-instance bar. The bars live only in tests/ and appear nowhere
in the environment, so there is nothing to read off or iterate against; the environment's validator
deliberately reports legality and cost but has no notion of a bar. Every bar is a cost the reference
solver actually achieves, so it is reachable by construction, and since it is at or above the true
optimum any genuinely optimal schedule clears it. All 24 must pass for reward 1. A fabricated or
padded schedule cannot pass: cost is recomputed from the ops rather than reported by the agent, and
a schedule that skips work fails legality rather than scoring well.
"""
category = "ML"
subcategory = "Training"
tags = ["rematerialization", "gradient-checkpointing", "scheduling", "optimization", "memory"]
expert_time_estimate_hours = 8
relevant_experience = """
I work on LLM training infrastructure, on the memory side: activation rematerialization and
gradient checkpointing policies, activation offload, and the scheduling work that decides what a
training step keeps resident and what it pays to rebuild. I have implemented checkpointing policies
that beat uniform spacing on real backbones with heterogeneous layer costs, and built the replay
harnesses used to prove a policy's peak memory and recompute overhead before it goes near a training
run, which is where this task's instance and schedule format comes from.
"""

[verifier]
timeout_sec = 600.0
environment_mode = "separate"

[agent]
timeout_sec = 10800.0

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
```
