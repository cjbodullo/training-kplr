# coupon-standing

## task.toml
```toml
artifacts = ["/app/standing.json"]

[task]
name = "afterquery/coupon-standing"

[metadata]
author_name = "Sayan Banerjee"
author_email = "sayanbanerjee.writodesk@gmail.com"
difficulty_explanation = """
Everything mechanical is in the container and AUDIT.md sets out the contract \
file by file and field by field. The range, the coupon library, the merchants' \
notices and the desk's own log all ship whole. The arbitrary parts of the \
procedure are published outright rather than withheld, because an unstated \
arbitrary choice is a coin toss and not a judgement: the audit date, that the \
range space is cloth x foam x frame x barrier x place with barrier being one of \
the three or none at all, that reach is worked the same way whatever the \
standing turns out to be, that a notice can only close a coupon burnt before \
it, that a coupon standing in for another must be open, of the same source and \
the same result, and that on equal reach the coupon with the higher id is the \
one spent. firstpass.ts runs and produces a well formed return. \
standing-check.ts runs and holds a return to its shape and to the arithmetic \
the desk can do without knowing the scheme. Twelve worked lines ship with their \
answers. \
\
What is not in the container is how far a coupon reaches. Eight readings are \
graded and every one was ablated over the 440 coupons by flipping it to the \
reading a careful person otherwise lands on, counting coupons moved: a coupon \
burnt on a back coated cloth rests on the coating and one burnt on a plain \
cloth rests on the mass (145). Foam density reads upward for combustion \
modified and downward for plain (343). A barrier cloth may be added to a coupon \
that carried none, but not behind a cloth that melts (98). A seat coupon \
carries to back and arm except off a sprung platform (57). Coupons group by \
platform and shell and the range name means nothing (405). A formulation notice \
closes earlier coupons on that cloth, a back coating notice closes only the ones \
with no barrier behind them, a shade card notice closes nothing (86). A FAIL \
settles every build that would itself have stood as evidence for it, which is \
the relation run backwards (73). And a coupon only stands in for another if \
releasing on it instead would put nothing new on the works order, which turns \
on the houses' notes and on OB-CHAR answering to no condition code at all (15). \
All eight blunt at once moves 420 of 440. \
\
The readings compound rather than stack. Reach is the size of a product of \
per axis sets, so a single axis read wrongly moves the number on nearly every \
coupon, and standing is decided by set containment between coupons, so the same \
error moves which coupons stand in for which. The FAIL direction runs the whole \
relation backwards, which exercises all five axis rules a second time and does \
NOT factor axis by axis - whether a build's barrier is admissible depends on \
that build's own cloth and whether its place is admissible on its own frame - so \
an agent that recovers the five rules still has to notice that the reverse \
direction cannot be computed the same cheap way. Grading is all or nothing over \
440 coupons and two fields. \
\
Nothing here can be self checked. There is no oracle for the scheme anywhere in \
the container. standing-check.ts passes the shipped first pass, which agrees \
with the sealed return on 0 of 440 coupons, and it says so about itself in its \
own header. The twelve practice lines are in the desk's daily ruling shape and \
not the return's, so no practice answer is ever a thing that could be returned, \
and each was selected constructively to be byte identical under all eight \
single flips and under all eight at once. \
\
Fairness is built as code. dev/ablate.py proves every reading is load bearing. \
dev/audit.py pins each reading to literal lines in the shipped evidence, 30 \
citations, and fails the build if a later edit removes one; it also replays all \
70 rows of the desk's log against the reference and counts, per reading, the \
rows that are IMPOSSIBLE under the blunt rival rather than merely consistent \
with the truth - 4 or more for every reading the log can speak to. dev/rivals.py \
implements eight rival readings of the PUBLISHED machinery and requires any that \
moves a coupon to be settled by a sentence still present in AUDIT.md; four of \
them move 84, 165, 87 and 23 coupons, so those sentences are load bearing and \
not decoration.
"""
solution_explanation = """
The method is to read the desk's log against the coupon library, and to read \
the three programs under downstream/ asking what the scheme has to be for what \
they do to make any sense. solution/reference.ts is the answer and its header \
lists all eight readings in order. \
\
The log gives seven of the eight. A TESTED row is a line the desk paid to have \
burnt, so nothing in the library reached it that day, and every coupon a rival \
reading says would have reached it is a coupon that rival is wrong about. A \
RELEASED row names the coupon a line went out on. A REFERRED row names a failed \
coupon that settled against it, and those are the cleanest of all: they cite \
coupons milder than the build, which cannot happen if a failed coupon settles \
forward the way a passed one carries forward. \
\
downstream/ gives the eighth and corroborates the rest. schedule.ts prints a \
coating and no mass for a coated cloth and a mass margin and no coating for a \
plain one, and asserts the margin renders positive; its foam margin takes its \
sign off the grade and is asserted positive too; it refuses to print a sprung \
seat coupon against anything but that seat; and its list of merchant notices \
since the coupon will not render a formulation notice, nor a back coating \
notice where no barrier sat behind it, while shade card notices print freely, \
which fixes all three scopes. goodsin.ts routes an order to a bench keyed on \
platform and shell with no range name in the key and refuses a coupon off \
another bench. Its table of incoming checks for a barrier added behind a cover \
has rows for NATURAL and BLEND and none at all for the two that melt. \
works-release.ts is the account of what a release puts on a works order: it \
issues the coupon's own build sheet in full first, so a CN-IL against a coupon \
that already carried the barrier picks the same cloth twice and the order is \
rejected; its CN-SEAM note has to name the cloth the coupon was not burnt on; \
its CN-XREF queue entry is the list of differing axes and an empty one is \
refused; and its switch over the condition codes is exhaustive on never, which \
is what says the vocabulary is closed and therefore that OB-CHAR answers to \
nothing. That last step is the eighth reading: a coupon whose only extra note \
is a char note puts nothing extra on any works order, so it can still stand in. \
\
Reach then falls out. For a PASS the relation factors one component an axis, so \
reach is a product of five counts. For a FAIL it does not, and the reference \
factors it into a (frame, place) component, a foam component and a (cloth, \
barrier) one instead. Standing is set containment between those components plus \
the notes test plus the published tie break. \
\
solve.sh installs the reference, writes /app/standing.json and runs the shipped \
shape check over it. dev/crosscheck.sh is the guard that matters: the sealed \
return was cut by dev/policy.py in Python and the oracle runs reference.ts in \
TypeScript, which are separate implementations, and the check asserts they agree \
on all 440 coupons. A mistake in one of them alone cannot become the answer.
"""
verification_explanation = """
What is graded is data, not code. The agent leaves /app/standing.json and the \
verifier reads it with json.load and compares plain dicts of strings and \
integers. Nothing the agent wrote is executed, imported or evaluated anywhere in \
the grader. There is no module to load, no interpreter shared with agent code, \
and no object whose __eq__ could reach a comparison. \
\
The sealed return exists only in the verifier image, under /tests, root owned \
and mode 0700. The agent's container holds the range, the library, the notices \
and the desk's log, which are all input, and no answer in any form: no \
reference, no generator, no worked return. The twelve practice answers that do \
ship are rulings on lines - a state, a governing coupon and a list of condition \
codes - which is not the shape of the return at all, so no practice answer is a \
thing that could be handed back; and each was selected to be byte identical \
under every single flip of every graded reading and under all of them at once, \
so they settle nothing. standing-check.ts reads only the agent's own file and \
the library beside it and knows nothing it could give away. \
\
Shape is checked first and it is at least as strict as the check that ships in \
the container: that the file parses to an object, that it covers exactly the 440 \
coupons and no others, that every standing is one of the three words, and that \
every reach is a whole number - not a bool - between zero and 69120. Then every \
coupon is compared on both fields. Reward is 1 only when the file reads, every \
coupon is there, every entry is well formed and all 440 match exactly. \
reward.txt is written from pytest's exit code on every path, including a missing \
file, unparseable JSON and a crash. \
\
The failure report is diagnostic rather than a bare count. It gives coupons out \
of 440 split by standing and by reach, prints the first twelve in full, and says \
what the submitted return actually is: whether it is the sealed answer with one \
named reading read the blunt way, whether it is closer to one of those than to \
the answer, and whether it is the shipped first pass. \
\
Measured here: the reference scores 1 with 440 of 440, the shipped first pass \
scores 0 and agrees on 0, a return that declares everything LIVE with reach 1 \
scores 0, a competent return with the mechanics exactly right and all eight \
readings read the natural way scores 0, and every cheat scores 0. Writing a \
reward file from inside the agent container achieves nothing, since the verifier \
runs in its own image and writes its own once pytest is dead.
"""
category = "Software"
subcategory = "Data engineering"
tags = ["typescript", "data-engineering", "reverse-engineering",
        "compliance", "legacy-systems", "node"]
expert_time_estimate_hours = 8
relevant_experience = """
I have spent most of my working life on the systems that sit between what a \
business physically does and what it is allowed to say about it, and a fair \
share of that has been evidence management for people who make things to a \
standard. Read across is the part nobody writes down and everybody has a \
settled opinion about. Two firms making the same product to the same standard \
will read the same test coupon differently and each will be certain there is \
only one sensible way to read it. \
\
The thing that took me longest to learn is that on a job like this the \
specification is not missing, it is somewhere you would not think to look, and \
here that is inside the programs that live off the answer. A schedule that \
prints a coating for one cloth and a mass for another has told you what the \
coupon rested on. A stores table with rows for two of the four cover classes \
and none for the other two has told you which builds the scheme never \
contemplated. A works order that would pick the same barrier cloth twice has \
told you what a condition code is for, and a condition vocabulary with nothing \
in it that answers to a char note has told you that a char note costs nothing. \
None of that was ever set down as a rule because nobody needed it set down. The \
person doing the work knew. \
\
The failure that cost me most was on the currency side. We rebuilt an evidence \
register that retired every report a supplier notice touched, on the reasonable \
view that a change is a change, and it took about eleven per cent of a live \
evidence library out of service overnight and put a fabricator on stop for a \
fortnight. Shade card notices are not formulation notices. The second one was \
quieter and worse. We read a substitution rule as symmetric because nothing \
said it was not, and released work on evidence that ran the wrong way. \
\
So the split here is the split the job has. All the machinery is handed over, \
because machinery is what a colleague gets on their first morning and nobody \
should be reverse engineering a column layout. The reading is not handed over, \
because there is nothing to hand over. The desk's log is what survives and the \
consumers are what survive, and counting a library against a scheme you \
invented yourself only confirms what you already believed.
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

## instruction.md
```
our scheme certification is up in november and this time they want the library
declared. not a list of what we hold. a standing against every coupon in it,
and a number against every coupon saying how much of the range that coupon is
actually carrying.

i run the cover desk at nettlebed. we make contract seating, healthcare and
education mostly, and a coupon here is one built assembly burnt against one
ignition source. frame, foam, cloth, barrier cloth or none, and where on the
chair it sits. we do not burn what we sell, nobody does, you would be testing
until the end of time. we burn a coupon and it stands for a range of builds
around itself.

there are four hundred and forty of them and i pay to have the live ones
witnessed again every cycle. that is the part that stings. i am fairly sure a
good number of those are being paid for twice, because somewhere else in the
library there is a coupon that already does everything they do and more, and
nobody has ever sat down and worked out which. others are dead and i am still
paying for them, because a merchant reformulated a cloth years ago and the
coupon went with it.

`/app/AUDIT.md` walks the folder and sets out exactly what the return has to
say. read that first, it is the contract. what i need out of you is
`/app/standing.json`, one entry per coupon, every coupon in
`library/coupons.json` and nothing else in there.

each entry is two things. `reach`, which is how many of the sixty nine thousand
one hundred and twenty range builds that coupon settles, a plain integer. and
`standing`, which is `CLOSED` if a merchant notice has killed it, `SPENT` if
another coupon in the library stands in for it completely so we need not
witness it again, and `LIVE` otherwise. AUDIT.md sets out what standing in for
completely means, and the arbitrary bits of it, the tie breaks and the like,
are written out there because they are arbitrary and somebody had to choose.

run `node standing-check.ts /app/standing.json` over whatever you produce. it
holds the file to its shape and does the arithmetic the desk can do without
knowing the scheme, and it says in its own output that it cannot tell you
whether a single reach is right.

here is the part i cannot hand you. how far a coupon reaches is not written
down. it never was. margaret ran this desk from 1998 and she ruled off what she
knew, and what she knew went with her, and the two who did it after her did it
by asking margaret. i have asked the houses and they will tell you about their
own coupons and nothing about our scheme.

what i do have is everything the desk did. `desk/log.tsv` is the log back to
2019, every line we worked, the day we worked it, and whether we released it or
referred it or gave up and paid for a coupon. a line we paid to have burnt is a
line nothing in the library reached that day. that is a fact about the scheme
even though nobody ever wrote the scheme down, and there are a lot of those
facts in that file. i have read it for two months and i can see there is a
system in it. i cannot see the system.

and there are three programs under `downstream/` that live off the desk's
rulings. works-release turns a ruling into a works order, schedule renders the
page the specifier's fire engineer reads, goodsin raises the stores check. none
of them runs here, they want platform packages that are not in this folder and
works-release wants an ERP session on top, but they are the only written
account of what any of this means. what they refuse to do is worth as much as
what they do. a page the portal will not render is a page that would have said
something untrue.

`desk/practice.json` has twelve worked lines with the answers beside them. they
are in the desk's daily shape, a ruling on a line, not the return's shape, and
they will not settle anything about how far a coupon reaches. work them anyway.
if you cannot reproduce those twelve then something mechanical is wrong and
there is no sense going further. `firstpass.ts` is where i got to alone, which
is a coupon reaching only the build it was burnt as. it runs, it satisfies the
shape check, and a coupon that reaches one build out of sixty nine thousand
would not have been worth burning.

the folder is typescript and node 24 runs the `.ts` files in it directly, no
install and no build step, so work in it if that suits. i do not mind what you
write it in. i want the json.

i will not pretend it is a small ask. take the log apart, take the three
programs apart, and declare the library.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
