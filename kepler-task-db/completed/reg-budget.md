# reg-budget (Software / Languages)

v2 built 2026-09-18, passed the full automatic pipeline the same day (user report). Local gates: oracle=1 (942 ops, budget 971), nop=0, cheat=0.

## task.toml

```toml
artifacts = ["/app/schedule.json"]

[task]
name = "afterquery/reg-budget"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "Fitting a computation into a handful of registers with no room to spill is the work a compiler backend engineer does for register starved targets: a constant time crypto core that must not touch memory, a GPU kernel whose occupancy collapses the moment it spills, an entry stub that runs before any stack exists. The shipped material is kernel.c, a straight line clang translation unit over 12 double inputs writing 80 outputs through four levels of shared intermediates, kernel.ll, its LLVM IR emitted by the clang in the image, and dag.json, the same computation as a normalized 174 node value graph (121 three operand nodes, 41 two operand nodes) with the two budgets, 7 registers and 971 operations. The kernel is synthetic, generated for this task so that nothing about it is online, but it is a real translation unit and has the shape of fused arithmetic code where a few dozen shared subexpressions feed many results. Evaluated straight through it keeps 60 values live against 7 registers, and the machine has no memory, so an overwritten value can only come back by being computed again from its operands, and a level three value costs up to 35 operations to rebuild from nothing. Recomputing every output from scratch would take 2065 operations even if it fit; the budget is 971. The numbers below are measured on the shipped graph and show where the difficulty sits. A depth first emitter that always gives the result a register of its own failed to fit 7 registers on every output order tried, whether it evicts the cheapest value or the one used furthest ahead; the deepest cones only fit when the destination takes over the register of an operand that has just died and the most expensive operand is evaluated first while registers are still free. With that in place, cheapest first eviction gives 3217 operations in source order, 3060 as the best of 500 random output orders and 2281 after a 3000 step pairwise swap hill climb; furthest next use eviction gives 2643, 2432 and 1754 on the same three searches; annealing the output order for 20000 steps on top of furthest next use stops near 1330 to 1410. Eviction that weighs recompute cost against next use, with next use corrected for consumers that are already resident, reaches about 1240 to 1280 at 20000 steps and 1080 to 1115 at 200000 steps when only the output order is searched. Getting under 971 took a joint search over the output order, a per value keep or evict bias, a per value operand priority and the cost weight, run for a million steps from several seeds. So the hard part is not writing an emitter, it is that the quantities interact: holding a shared value saves recomputation but removes a register from every deeper cone evaluated meanwhile, which can make that cone unfittable or force other values out, and the right choice for one value depends on the order of the outputs and on what else is held. This is black pebbling with recomputation, PSPACE complete in general, and the feasible set is defined by replaying the schedule, not by static constraints a stock solver accepts. The result is pass or fail, so a schedule that is 5 percent over is worth nothing."
solution_explanation = "Read dag.json for the graph and the two budgets. solve.sh first checks kernel.c with clang, then builds the searcher remat.c with the same clang (the search is millions of schedule decodes, too slow for an interpreter) and runs schedule.py, which feeds it the graph, runs 8 fixed seeds 4 at a time, keeps the shortest schedule, replays it against the graph as a legality check and writes /app/schedule.json. The searcher has two layers. The decoder turns a plan into a concrete schedule: it walks the outputs in plan order and materialises each one depth first, evaluating the most expensive operand first because the operand evaluated last is evaluated while its siblings are pinned; when it needs a register it evicts the resident value that is cheapest to lose, scoring distance to next use against recompute cost plus a per value bias, where a value whose remaining consumers inside the current output are already resident or done is treated as not needed until a later output; and it lets the destination take the register of one of the node's own operands once that operand is dead, without which the deepest cones do not fit 7 registers at all. The outer layer is simulated annealing over the plan: the output order (swaps and reinsertion), the per value eviction bias, a per value operand priority that reorders the operands of its consumers, and the global cost weight, one million steps per seed with a linear cooling schedule. Everything is deterministic: a fixed xorshift generator per seed, fixed step counts, and an exponential for the accept test written in plain IEEE arithmetic and built with -ffp-contract=off so the run is bit identical across compilers, C libraries and CPUs. The eight seeds finish between 942 and 984 operations, the best is 942, and the budget of 971 is that plus 3 percent. It runs in about 15 minutes on 4 cores."
verification_explanation = "The deliverable is a schedule, so the verifier runs nothing the agent wrote. It reads /app/schedule.json and replays it against the value graph baked into the verifier image: every operation must have its input nodes resident in registers at that step, no register index outside 0..registers-1 is ever written, the schedule is no longer than op_budget, and every output node is produced. Operands are read before the destination is written, so an operation may overwrite one of its own operands, as the instruction states. It then executes the schedule with real arithmetic on several random input vectors and requires each output value to equal the graph's true value, so a schedule that is structurally valid but computes the wrong thing fails. Grading is all or nothing. There is no sealed answer to leak: the check is defined entirely by the shipped graph and the two budgets, which are public. The verifier runs in its own separate container, the reward directory is root owned, and reward.txt is written on every path including a crash."
category = "Software"
subcategory = "Languages"
tags = ["compilers", "register-allocation", "rematerialization", "pebbling", "clang"]
expert_time_estimate_hours = 10
relevant_experience = "I have written compiler backends and hand scheduled register starved kernels, the kind where the allocator would spill and you cannot afford the memory traffic, so you rematerialize instead. The judgment that is never mechanical is exactly this tradeoff: which values are worth keeping live because they feed many later uses, and which are cheap enough to recompute that holding them wastes a register. I have done it by hand for constant time primitives and for inner loops where a single extra spill changed the measured throughput."

[verifier]
timeout_sec = 300.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 1800.0
cpus = 4
memory_mb = 4096
storage_mb = 10240
gpus = 0
```

## instruction.md

```
i need a schedule that evaluates a straight line numeric kernel on a machine with very few
registers and no memory to spill into. everything you need is under /app/problem.

kernel.c is the real computation, a straight line function over 12 double inputs that writes 80
double outputs. i compiled it with clang and left the ir next to it in kernel.ll if you want to
read it. dag.json is the same computation as a normalized value graph and it is what the grader
uses. it lists every value as a node with an op (in, add, mul, sub) and the input nodes it is
computed from, then the list of output nodes, then two budgets: registers is how many registers
you have, op_budget is how many operations your schedule may use.

the machine is simple. there are `registers` registers, numbered 0 up. each register holds one
value. an operation writes one node into one register, and after it that register holds that node.
to compute a node that is not an input, every one of its input nodes has to be sitting in some
register at that moment. an input node just loads that input into a register. writing a register
throws away whatever was in it. an operation may write into a register that is holding one of its
own inputs, the inputs are read before the write lands. there is no memory and no stack, so the
only way to keep a value is to keep it in a register, and the only way to get a value back after
you have overwritten it is to compute it again from its inputs. an output counts as produced the
moment you compute it, you do not have to keep outputs sitting in registers at the end.

here is the part that makes it work. the kernel has far more than `registers` values that would
be alive at once if you just walked it start to finish, so a plain evaluation does not fit. you
have to recompute values you cannot afford to hold, and you have to do it without blowing the
operation budget. so it is a trade. keep too much and you run out of registers, recompute too
freely and you run past op_budget. i want a schedule that lands inside both.

write /app/schedule.json. it is an object with one key "ops" whose value is a list, in execution
order, of steps like {"r": 2, "node": "m5"}, meaning compute node m5 into register 2. use the node
ids exactly as they appear in dag.json. your schedule must produce every output, never write a
register index outside 0..registers-1, keep every operation's inputs resident when it runs, and
use at most op_budget operations. i check it by replaying it on the graph and then running it on
real inputs to confirm the numbers come out right. it is all or nothing.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
