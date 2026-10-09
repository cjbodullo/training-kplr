# crash-bucket — APPROVED THROUGH PIPELINE (Needs Review) 2026-07-31

submissionId: hO5dTO8FSaBOZI9xMh8Y | Software / Systems | $175
difficultyProbe: in_band, rewards [1,0,0,1,1,1,1,1] = 6/8
easinessProbe: 1/3 | cheatProbe: hacked=False | trajectoryReview: passed

## instruction.md
```
cairnd is the box that turns a crash dump into a bucket key, and it goes back to the leasing company at the end of the quarter. every thing we run off crash data reads those keys. duplicate counts, the regression alerts, the board release management looks at on a monday, the rota that drops a bucket in front of whichever team owns it. none of that stores dumps. it stores keys.

so what i need is not a better fingerprinter. i need the same one. a key out of the port has to be the string cairnd would have written, character for character, or the board stops joining crashes to their own history and every bucket we have open forks into two.

the port lives in /app/triage.py. `bucket(report)` takes one decoded report as a dict and gives back the key as a str. that file is already there and it already runs. it does the nine stages in /app/CAIRN.md in the order the note gives them, and it is clean across the whole queue in /app/queue. it is also wrong, in ways i cannot list for you. wherever rev 11 went quiet the person who started this took the flattest reading available and moved on. sometimes flat is what the box does. often it is not, and the note is worst exactly where two of its rules meet or where a stage runs out of input to work on.

cairnd itself is still up, on $CAIRN_URL, and it will fingerprint anything you send it. that is the only oracle in this container and it is metered, because the support contract dies with the hardware. one unit per frame you submit, counted across every thread in the report, four units minimum per report. a submission that would run past what is left gets refused whole and costs you nothing. the counter is on the unit's own disk. restarting it, or your container, gives back nothing, and there is no reset. `python3 /app/probe.py quota` tells you where you stand. i will say the obvious thing once: the twelve reports in /app/queue come to more frames than the whole allowance, so feeding it real traffic and reading the answers off is not a plan. work out what you are asking before you spend anything on asking it.

/app/gencrash.py is the dumper's own generator, so reports you build with it look exactly like what the board is full of and exactly like what your port gets judged on. only the seeds are different.

grading is forty reports you have not seen, drawn from seeds that are not in this container. your `bucket` runs against every one of them and each key is compared byte for byte with what the real cairnd produces. forty out of forty is a pass. thirty nine is a fail, same as zero, and there is no partial credit anywhere in this, so a rule you got right in eleven cases and wrong in the twelfth costs you the whole thing.

one last thing. the grader holds its own copy of cairn and burns whatever is left on the meter before it starts, so calling out to the sidecar at grading time returns nothing and hunting the container for a reference implementation is time you will not get back. there isn't one in here. the answer only exists in the box, and only while you can still afford to ask it.

You have 18000 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```

## task.toml
```toml
artifacts = ["/app/triage.py"]

[task]
name = "afterquery/crash-bucket"

[metadata]
author_name = "Sayan Banerjee"
author_email = "sayanbanerjee.writodesk@gmail.com"
difficulty_explanation = """
The container hands over the mechanism and withholds the policy. CAIRN.md gives \
the report wire format, the module classification lists, the handler, check and \
entry symbol sets, the key grammar, and all nine stages of the fingerprint \
pipeline in the order they run, with two fully worked examples. The starting \
/app/triage.py implements every one of those stages already and runs clean on \
the whole shipped queue, so nobody spends the clock rebuilding scaffolding, and \
/app/gencrash.py is the dumper's own generator so the traffic distribution is \
not a secret either. What is missing is ten conditional decisions, and unlike \
the published stages they are not listed anywhere: whether signal delivery \
frames come off an abort as well as a signal and how deep the handler is looked \
for, whether a runtime frame carrying a source line is still noise, what an \
unsymbolised physical frame behind an inline contributes and whether its inlines \
outlive it, which order inlines come out in, where a repeated run folds and \
where a two cycle folds, whether template arguments come off third party symbols \
as well as first party ones, what happens to a lambda in a third party module, \
when a thread name is appended to the reason part, whether the entry frame \
itself is cut when cutting it would leave nothing, and when a token is written \
bare instead of qualified with its module. Every one is a conjunction, firing \
only where two features of the report meet, so an agent that probes one feature \
at a time derives a rule that is right about its probe and wrong about the \
graded set. All ten were ablated: flipping one alone to its weakest plausible \
alternative moves between 4 and 54 percent of 400 generated reports, so none of \
them is decoration, and the shipped stub agrees with the unit on 55 of 400. \
This is a third cut, and the two earlier ones are why I trust the number. At \
sixteen hidden decisions the difficulty probe measured too hard at 0 of 8, but \
nobody was stuck: every attempt finished inside a fifth of the time budget, \
spent the meter out, reproduced 58 to 62 of its own probe answers, and scored 14 \
to 34 of 40. At thirteen it was still 0 of 8 and the scores moved up to 23, 28, \
30, 31, 34 and 38 of 40, with the best attempt failing on exactly two rules. \
Both times the per trial analysis named which decisions did the killing, and \
both times those decisions were written into CAIRN.md and into the shipped stub: \
first the depth cut, the CHECK reason part and the truncation marker, then \
thread selection, the allocator exception and offset rounding. The two attempts \
that came closest failed on nothing else, so at ten the same trials land on 40. \
The meter never moved, because it was never the binding thing: agents spent 277 \
to 280 of 280 at every cut and used 36 to 57 minutes of a 300 minute budget. \
The unit is up and will fingerprint anything, which is what makes this fair and \
also what makes it hard, because it is metered: 280 frames for the whole \
engagement, counted across every thread in what you submit, floored at four per \
report, a submission that would overrun refused whole, persisted on a volume, \
never reset. The twelve reports shipped in /app/queue are 290 frames between \
them, so replaying the examples alone costs more than the entire allowance. I \
measured both strategies with a fitter far stronger than any agent, one handed \
the exact axis list and the exact candidate value for each axis. Spending its \
frames on shaped probes it recovers the policy in 49 to 77 frames. Spending them \
on ordinary generated traffic it recovers nothing at 280 or at 450 frames and \
only reaches 3 of 8 seeds at 600. \
Last piece is that grading is exact over forty reports built from two seeds that \
live only in the verifier, with no local oracle for them once the meter is gone. \
Agreeing with the unit on everything you thought to ask is exactly the state a \
wrong port is in, and it is the state every losing attempt so far has finished \
in, several of them reproducing every key they had bought.
"""


solution_explanation = """
Read CAIRN.md, keep the pipeline that is already in /app/triage.py, then spend \
the frame budget settling the ten edges and write the answers into the code. \
dev/probe_plan.py in the authoring tree is a worked campaign: shaped reports \
covering every candidate distinction, 49 to 77 frames depending on seed. \
The answers: an unflagged report is keyed from the first thread whose innermost \
non runtime frame is first party, dropping to thread 0 only if none qualifies. \
Delivery frames come off only on a signal and only if a handler symbol appears \
in the innermost six, and everything up to and including the outermost such \
frame goes. A runtime frame carrying a source line is kept. Allocator frames are \
dropped unless the innermost frame of the walk is itself allocator, in which case \
they all stay. Inlines come out innermost first; a physical frame that did not \
symbolise contributes nothing of its own when it has inlines, and when a \
physical frame is dropped its inlines go with it. A lambda body in a third party \
module is dropped outright, and in a first party module it renders with the \
compiler ordinal. Parameter lists always come off, template arguments only for \
first party modules. An unsymbolised frame is module+0xoffset with the offset \
rounded down to a multiple of 16 when the module has a build id and exact when \
it does not. A token is qualified with its module only when that module differs \
from the previous token's, so a run inside one library reads bare. A repeated run \
folds at three, not two, and a two cycle folds at six. Depth is three, widening \
to five when the first three tokens all came from one module. An abort whose \
check handler sits in the innermost four frames reads CHECK@file:line, taking \
the first source line outside the handler. A thread name is appended when it is \
neither main nor an auto generated Thread-N. The entry frame is cut along with \
everything outside it unless that would leave fewer than two units. A truncated \
stack gets a trailing + only when it ran out before the depth cut did. \
solution/triage.py is that implementation and solve.sh installs it at \
/app/triage.py. It reproduces the sealed reference on 2800 generated reports \
across seven seeds with zero mismatches.
"""
verification_explanation = """
The reference engine, the generator and the two seeds behind the graded reports \
exist only in the verifier image, which is root owned mode 0700, so there is \
nothing in the agent's container to read the answers off, and cairnd does not \
hand them over either. Forty reports are built from those seeds and none of them \
is among the twelve shipped. \
The agent's module is never imported into the grader. It is copied out of /app \
into a scratch directory on its own, so the rest of its container is off the \
import path, and run once over every graded report in a child launched with \
python3 -I as uid 65534 with an empty supplementary group set, in its own \
session, with a neutral working directory, an environment stripped to PATH and \
HOME, and hard RLIMIT_AS and RLIMIT_NPROC. That child only writes key files. \
Every reference key is computed in the trusted parent after the child has \
exited and compared byte for byte, so no frame in the agent's process ever holds \
an expected value and there is no status it can forge: a report with no output \
simply fails. Before any of that the parent burns cairnd's remaining allowance \
through its /seal path, so a module that answers by proxying to the sidecar gets \
nothing even if the sidecar is still up at verify time. Reward is 1 only if the \
module imports, bucket() raises on nothing, and all forty keys match, and \
reward.txt is written from pytest's exit code in the parent on every path \
including a crash. \
Confirmed locally: the reference implementation scores 1 with all 40 keys \
matching, the shipped starting stub matches 0 of the 40, each of the ten \
decisions was separately confirmed to move at least 4 percent of generated \
reports on its own, and cheat attempts that proxy to cairnd, hunt the filesystem \
for a reference, forge the reward file and exit, or read the grading scratch \
directory all score 0.
"""
category = "Software"
subcategory = "Systems"
tags = ["crash-triage", "stack-traces", "reverse-engineering", "black-box-inference", "developer-tooling", "python"]
expert_time_estimate_hours = 7
relevant_experience = """
Replacing a diagnostics component while keeping its output string identical is a \
job I have done, and the reason is always the same: something downstream was \
built against the old behaviour and nobody is paying to rebuild it. In our case \
it was a crash board with two years of bucket history in it and an alerting rule \
that fired on the rate of change of a bucket's count. The fingerprinter itself is \
never the hard part. Walk the frames, drop the noise, take the top few, join them \
up. An afternoon. The hard part is the policy nobody wrote down, and specifically \
the conditional policy, the rules that only fire where two things about a report \
meet: a libc frame that stays because we happen to have symbols for it, an \
allocator frame that stays only when the fault was actually in the allocator, a \
depth cut that widens when the whole head of the stack is one library. I have \
shipped a signature port that agreed with the original on every dump I had and \
then split the top bucket on the board in half the following week, because the \
original stopped qualifying a token with its module once the module stopped \
changing. \
The metering is from the same world. You rarely get to hammer the box you are \
replacing, because it is retired or licensed or it is the one unit nobody is \
allowed to disturb, and what separates a fast port from a slow one is designing \
the experiment before you spend the call. I built the environment around that on \
purpose: everything is determinable from the unit, a complete campaign costs \
under a quarter of the budget, and grinding real traffic does not fit inside it.
"""

[verifier]
timeout_sec = 3600.0
environment_mode = "separate"

[agent]
timeout_sec = 18000.0

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
```
