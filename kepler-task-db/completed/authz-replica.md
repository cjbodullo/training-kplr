# authz-replica (Software / Languages) — passed the automated pipeline 2026-07-29 as jKuaccvtyvt3vmClKP3x

difficulty 3/8 in_band | easiness 0/3 | cheat probe defeated | quality pass | Needs Review

Third attempt. v1 `Sy3wzKmnatdaR43Nb2uQ` died difficulty 0/8 too_hard on 24 hidden decisions;
v2 `hStQujIT8Q0RIbNAJ9cW` died cheat_probe hacked=true on a trial that scored reward 0;
v3 cut the graded unknowns to 16, named them as numbered open questions, and killed the
graded child's whole process group before reading its answers.

## instruction.md
```markdown
we are pulling the meridian ac-4 out of the auth path and i need the part that actually decides things replaced, in python, this week.

the unit takes one policy bundle plus one request and answers permit or deny. nothing else. our bundles look like the shape in /app/SPEC.md, and there is a bundle and a few requests under /app/samples if you want something concrete to hold. what SPEC.md will not tell you is what any of it means, because it is an interface document. the vendor folded, the semantics manual never existed, and the two people here who knew the thing left. so the syntax is settled and the behaviour is not.

the unit itself is still racked and still answering, on host ac4 port 8080. ac4q on your path talks to it, ac4client.py is the same thing from python, and SPEC.md has the endpoint. here is the catch. it is still in the serving path for one tenant we have not migrated, and the support contract meters it. you get 600 decisions for the whole job. status is free, decisions are not, a batch that would run past the meter is refused whole instead of partly charged, and nothing refills, not on a restart, not tomorrow. so ask questions you want the answer to.

write /app/engine.py. it exports decide(bundle, request), takes both as ordinary parsed json, returns the string permit or the string deny. keep it self contained, standard library only, because only that one file gets picked up. i will run it against bundles from our own tenants that you have never seen, written by people who use every corner of that syntax, and check every request in them against what the unit says. all of them have to match. a decision point that is right most of the time is worse than none, so this is pass or fail on the whole set.

two things i would tell a new hire here. the box is honest and it will answer anything you put to it, but it will never tell you which question was the one that mattered. and we have been bitten more than once by assuming it works like the cloud iam everybody learned on. it does not, in more places than one, and the places that cost us were never the ones we would have guessed.

last thing. by the time your code is graded the unit is gone from the network. no port, no client, no second look. whatever you learned has to already be in the file.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```

## task.toml
```toml
artifacts = ["/app/engine.py"]

[task]
name = "afterquery/authz-replica"

[metadata]
author_name = "Sayan Banerjee"
author_email = "sayanbanerjee.writodesk@gmail.com"
difficulty_explanation = """
The container carries the appliance's interface reference. It fixes every shape \
in the policy language, writes down the behaviour anybody ever documented, and \
then closes with sixteen questions it never answered. Those sixteen are the task, \
and they are stated as questions on purpose: nobody is being asked to guess that \
an axis exists, only to find out what the unit does on it. Whether a single \
wildcard may cross a segment break when the double one may. What a statement \
with no actions covers, and what one with no resources covers, which are not the \
same answer. What happens to a statement that names both action forms. Which \
statement of a policy answers when two of them match. How policies attached at \
different distances combine and which of those distances a forbid actually wins \
in. How many hops of group nesting count. What a boundary does with forbid \
statements of its own. What a condition key the request does not carry means to \
each operator. What a value the unit cannot type for a numeric operator does, and \
what an operator it does not know does. Whether an attribute reference expands \
inside a condition value, whether a trailing separator is normalised away, what a \
list valued key means to a one value operator, what set_all does with nothing to \
check, and what a principal the bundle never mentions gets. Each of the sixteen \
was ablated on its own against the \
graded battery: flipping any single one to a rival reading breaks between four \
and fifteen of the 477 graded requests, spread over at least four of the sixteen \
bundles, so nothing graded is decoration. An engine that answers all twelve the \
way the familiar cloud IAM would is wrong on 115 of 477 requests and misses on all \
sixteen bundles. \
Four of the sixteen cannot be read off a one statement policy at all. Whether the \
unit skips a statement it dislikes or drops the whole document is invisible \
unless the probe carries a sibling statement that would otherwise have matched, \
and that shape decides three separate questions which do not have the same \
answer: a numeric value it cannot type kills the policy, an unusable CIDR is only \
a miss, an operator it never heard of is waved through. How attachments combine \
needs two policies at different distances. Designing those probes is the work. \
The port is up and it answers anything, which is what makes this fair and also \
what makes it hard, because it is metered. Six hundred decisions for the whole \
engagement, never refilled. That number came from measurement. A differential \
fitter that is handed fifteen of the sixteen answers for free and only has to \
separate the last one by fuzzing needs a median of 19 to 2878 probes depending on \
which question it is chasing, and for the condition value expansion it separated \
it in only two of five attacker seeds inside 4000 probes. At six hundred units \
that fitter, which is strictly stronger than anything fitting jointly, still has \
three or four questions open. Directed work is far cheaper: the experiment in \
solution/probe.py isolates one question at a time and settles all sixteen in \
thirty one units. The budget is not a wall in front of a solvable problem, it is \
the difference between designing the experiment and sampling the box. \
Grading is all or nothing over sixteen bundles and 477 requests built from a seed \
that exists only in the verifier, with no local oracle for any of it.
"""
solution_explanation = """
Read the reference, work down its sixteen open questions, spend the meter on one \
experiment per question, then write the model. solution/probe.py is that \
experiment and it costs thirty one of the six hundred units: a policy whose two \
statements carry a single and a double wildcard, a statement missing each of its \
pattern lists in turn, a two statement policy whose first statement is the \
awkward one and whose second is a sibling that says whether the document \
survived, a policy with a permit written above a forbid, the same grant attached \
directly and through three levels of group and through star, a boundary carrying \
a forbid of its own, and three sibling probes for the missing key, the untypable \
number and the unknown operator, then one more bundle for the trailing separator, \
the list valued key and set_all on nothing, and a last request from a principal \
the bundle never mentions. \
What comes out: a single star covers a run with no separator in it while the \
double star covers anything; a statement with no action list covers every action \
while one with no resource list covers none; a statement carrying both action \
forms drops its whole policy; a policy answers with the first of its statements \
that has something to say, so a forbid written below a matching permit never \
fires; the nearest attachment decides and a forbid only wins among policies at \
the same distance, so a permit attached to the principal survives a forbid \
attached to their group; nesting is followed two hops; a boundary reads only its \
permits; a missing key reads as the empty string under the string operators and \
fails everything else; a value the unit cannot use for a numeric operator drops \
the whole policy even when the statement holding it would never have matched; an \
unknown operator is waved through as satisfied; and an attribute reference \
expands in patterns, which the reference says, but not inside a condition value, \
which it does not; one trailing separator is trimmed off the request resource; a \
list valued key satisfies a one value operator when any element does while \
set_all on nothing is false; and a principal the bundle never mentions is \
answered as an anonymous one. solution/engine.py is that model, written from scratch against \
the appliance rather than derived from it, and it agrees with the unit on all 477 \
graded requests and on 36000 fuzzed ones. solve.sh re-runs the experiment against \
the live port, fails loudly if the unit disagrees with what the model was written \
for, and installs it at /app/engine.py.
"""
verification_explanation = """
The appliance behaviour, the bundle generator and the seed behind the graded \
battery exist only in the verifier image, which is root owned mode 0700. Nothing \
in the agent's container carries them and the port does not hand them over \
either: sixteen bundles and 477 requests are built from that seed, with every \
identifier, path, attribute value, context key and block composition drawn from \
it, so nothing about a graded bundle can be memorised from the sample documents \
or from probing. \
The agent's module is never imported into the grader. It is copied out of /app \
into a scratch directory on its own, so the rest of its container is off the \
import path, and run once over the whole battery in a child launched as uid \
65534 with an empty supplementary group set, in its own session, with a neutral \
working directory, an environment stripped to PATH and HOME, and hard CPU, \
address space and process limits. That child only writes decision strings to a \
file. Once it has been waited on, its whole process group is killed and the \
answer file is read and then unlinked, so nothing of the agent's is alive while \
the answers are read and nothing can rewrite them afterwards; an answer is only \
accepted when it is exactly a string. Every reference decision is computed in the \
trusted parent after the child is gone and compared string for string, so no \
process of the agent's ever holds an expected answer and there is no status it \
can forge: a request with no answer simply fails. Before any of that the verifier zeroes the unit's meter \
through its seal endpoint, and the verifier container has no route to the \
appliance in the first place, so a submission that tries to answer by proxying to \
the decision port gets nothing. Reward is 1 only if the module loads, decide() \
returns permit or deny for every one of the 477 requests, the answers are not all \
the same string, and every one of them matches; reward.txt is written from \
pytest's exit code in the parent on every path including a crash. \
Confirmed locally: the reference model scores 1 with all 477 requests matching, \
the shipped stub scores 0, each of the sixteen open questions was separately \
confirmed to break at least four graded requests on its own, and cheat attempts \
that proxy to the appliance at verify time, walk the grader's frames and garbage \
collector for the answers, leave a detached process behind to rewrite the answer \
file after the run, forge a reward and overwrite the grader's files, or implement \
the familiar cloud IAM reading of the reference without measuring anything, all \
score 0.
"""
category = "Software"
subcategory = "Languages"
tags = ["authorization", "policy-engine", "reverse-engineering", "black-box-inference", "experiment-design", "python"]
expert_time_estimate_hours = 7
relevant_experience = """
Replacing a decision point you cannot read, against policy you did not write, is \
work I have had to do more than once, and authorization is the worst version of \
it because being nearly right is indistinguishable from being right until the \
day it is not. The habits this task grades are the ones that decide whether that \
migration goes well. The policy language is never the hard part. The hard part \
is that the interesting behaviour lives in the corners where two features meet, \
and none of those corners are in any document: a deny that loses to a grant \
attached closer to the user, a boundary that quietly ignores its own deny, a \
condition the engine cannot type taking the whole document down with it rather \
than just that statement. I have shipped a migration where the replacement \
treated a missing context key as a failed condition while the old engine read it \
as an empty string, which flipped a handful of deny rules into permits for \
exactly the requests that carried no context, and it took an audit to find. \
The metering is from the same world. You rarely get to hammer the appliance you \
are copying, because it is in the serving path or it is billed per call or both, \
and the thing that separates a good interop engineer from a slow one is \
designing the experiment before spending the call. I built the environment \
around that deliberately: everything is determinable from the port, a directed \
plan pins the whole model in a twelfth of the budget, and undirected fitting does \
not fit in the budget at all.
"""

[verifier]
timeout_sec = 1800.0
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
