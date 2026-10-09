# atomicity-retrofit (Software / Systems)

Built 2026-07-28. Local gates: oracle=1 x2, nop=0, 5 cheats=0.

## task.toml

```toml
artifacts = ["/app/depot"]

[task]
name = "afterquery/atomicity-retrofit"

[metadata]
author_name = "Sayan Banerjee"
author_email = "sayanbanerjee.writodesk@gmail.com"
difficulty_explanation = """
The engine is correct and the agent is not looking for a bug, so none of the \
usual debugging moves apply. What has to be produced is a locking design over \
about nine hundred lines of engine: which lock guards which piece of state, in \
what order locks may be taken, and what the two composite operations and the \
five maintenance passes are allowed to hold while they run. \
Two requirements pull against each other and that is the whole task. \
Correctness pushes toward holding more, for longer. The makespan budget pushes \
the other way: measured on this bundle, one lock around every operation and \
every maintenance pass runs at 3.4x to 3.6x the reference (3002/2869/2985 \
against 866/793/799), and a lock per structure held for a whole operation is \
worth nothing over that, since it serialises identically. The budget sits at \
1.35x the reference, so every coarse answer is excluded by a wide margin and \
the only designs that fit are ones that let disjoint work overlap. \
Fine-grained locking is where the difficulty actually bites. Operations that \
start from an item id cannot know which bin, tag or owner lock they need until \
they have read the item, and that read is not protected, so the obvious \
implementation locks the wrong thing when the item moves in between. I hit \
this myself while building the reference: it passed 237 of 240 randomised \
schedules before the check caught it. Revalidating under the locks fixes \
correctness and introduces the second trap, because a plain retry loop starves \
under a scheduler that keeps invalidating it; my own first attempt livelocked \
and had to be bounded by a mechanism that stops new operations from starting. \
Neither failure is visible in ordinary testing. \
The maintenance passes are the third front. They recompute derived state from \
items and write it back, so a pass that observes a half-finished operation \
bakes the wrong total in permanently, and no later pass notices. Deleting the \
passes makes all of that go away and lowers the makespan, so the suite damages \
derived state on purpose and requires each pass to repair it. \
Grading is all or nothing over 18 workloads x 18 schedules, 3 makespan \
budgets and 4 repair checks, and the schedules include one that hands the \
token to a different session at every single opportunity.
"""
solution_explanation = """
Assign a guard to every piece of state: a lock per bin covering the items \
currently in it together with that bin's totals and membership, a lock per tag \
over the tag index, a lock per owner over the owner index and the quota, one \
for id allocation and one for the journal. Fix a single acquisition order over \
those classes so no cycle can form, and take the id and journal locks at the \
point of use rather than for a whole operation, since holding the journal \
across an operation serialises every writer on it and puts the makespan back \
where the global lock was. \
Operations keyed by an item id read the record first, derive their lock set \
from it, take the locks in order, then read the record again and start over if \
the key set implied by it changed. The retry is bounded by a gate that every \
operation passes through before it begins: after a few failed attempts the \
retrying operation holds the gate, which stops new operations from starting, \
lets the few in flight drain, and guarantees the next revalidation sees state \
nothing can still change. \
The two composite operations hold both bin locks for their whole run and do \
their moves inline instead of calling back into move(), which would try to \
take a lock the operation already holds. Each maintenance pass takes the one \
guard for the piece it rebuilds; the unprotected scan of items it does is safe \
because a pass only acts on records whose key it holds. Quota checks are \
check-then-act and are covered by holding the owner lock across both halves. \
Reference makespan is 866/793/799 against budgets of 1169/1071/1079.
"""
verification_explanation = """
The engine runs in a child process with the verifier's own copy of the runtime \
ahead of /app on the path, as uid 65534 where setpriv is available, in a \
scratch directory that holds none of the grader's files. The child returns \
observations only. Every judgement is made in the parent, which owns a \
sequential reference model written independently of the engine on plain dicts. \
Correctness is linearizability, not an invariant check: for each of 18 sealed \
workloads under each of 18 sealed schedules, the parent searches for an \
interleaving of the recorded operations that respects each session's own order \
and reproduces every recorded result and the final state. Setup is replayed \
through the public API rather than installed as a state dump, and the final \
state is read back through the public read operations, so the read path is \
exercised too. Deadlock and non-termination are failures. \
Makespan is not taken from the graded process. The child emits its event log \
and the parent replays it through its own clock model, rejecting logs that are \
not internally consistent (a lock acquired while held, released by a session \
that does not hold it, negative costs, locks still held at the end) and \
rejecting runs that charge less work than the workload requires. \
Four repair checks damage a piece of derived state, run the pass that owns it \
and require the correct value back, which is what stops the passes being \
deleted. All 25 tests must pass; reward.txt is written from pytest's exit \
status in the parent on every path, including crashes.
"""
category = "Software"
subcategory = "Systems"
tags = ["concurrency", "linearizability", "locking", "python", "performance"]
expert_time_estimate_hours = 9
relevant_experience = """
I build and grade concurrent storage and execution engines. For this bundle I \
wrote the cooperative runtime (token passing scheduler over threads, virtual \
clock, lock model), the depot engine and its maintenance passes, the \
independent reference model, and the linearizability search used for grading. \
Before building it I measured the design on a smaller prototype: detection \
rates for four plausible-wrong locking strategies across three scheduling \
policies over 5040 runs, and the makespan penalty for coarse locking. That \
prototype is what told me a lock per structure is worth exactly nothing over a \
single global lock, which is the fact the budget is placed around.
"""

[verifier]
timeout_sec = 10800.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
```

## instruction.md

```markdown
our depot engine has only ever had one session inside it at a time. that is the thing i need changed. the code is `/app/depot` and it is correct as it stands, so i am not asking you to hunt for bugs in it. i am asking you to make it survive being driven by several sessions at once.

it runs on `/app/runtime`, which is ours, and `/app/RUNTIME.md` documents it. read that first, it is short. the part that matters is that one session runs at a time and every runtime call is a place where the scheduler can take the token away and hand it to somebody else. between two runtime calls nothing can interrupt you. at a runtime call anything can. `/app/demo.py` shows how the engine gets driven.

here is what has to be true when you are done.

every public operation on `Depot` has to look atomic. i mean that in the ordinary sense. take whatever results the sessions got back, and the state the depot ended up in, and there has to be some order of those operations, run one after another with nothing overlapping, that produces exactly those results and exactly that state. if no such order exists then something tore. that covers `put`, `drop`, `move`, `retag`, `chown`, `resize`, `rebalance`, `transfer`, `bin_stats`, `by_tag`, `by_owner`, `usage` and `journal_tail`.

the passes in `Maint` count too, and they are the part i would expect somebody to get wrong, so read them properly before you start. they recompute derived state from `items` and write it back, they run while client sessions are working, and they have to stay invisible. they also have to keep doing their job. i damage a piece of derived state on purpose, run the pass that owns it, and check it came back right, so making them return early is not an option.

it has to finish. a run that deadlocks is a failure. so is a run that keeps going round and never terminates. the runtime stops that one at its step budget instead of hanging forever, and i count it against you either way.

and it has to be quick. i measure makespan under `FairPolicy`, on workloads you do not get to see, and there is a budget. this is where i expect your time to go, because the correctness half of this has an obvious answer that does not fit the budget. one lock around everything is that answer. it is not the one i want.

some rules. leave `/app/runtime` alone, i grade against my own copy and edits to yours are ignored. locks come from the runtime and nowhere else, so no `threading`, no `asyncio`, no `multiprocessing`, no spin flags of your own invention. shared depot state stays in runtime `Map` objects. if you park it in a plain dict or a module global it simply will not be there when i read the final state back. keep the public method names and signatures as they are, keep the `Store` attribute names (`items`, `bins`, `binidx`, `tagidx`, `owneridx`, `quota`, `journal`, `limits`, `meta`), and keep single session behaviour identical to what it does today, because one session on its own still has to give the answers it gives now. new files under `/app/depot` are fine.

i grade on held out workloads, under schedules you have not seen, and every one of them has to pass.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
