# pgwire-crash-state — archived bundle manifest

## task.toml
```toml
artifacts = ["/app/state.json"]

[task]
name = "afterquery/pgwire-crash-state"

[metadata]
author_name = "Anand Pahade"
author_email = "bryandavidson737@gmail.com"
difficulty_explanation = """
The material is a real libpcap capture of real postgres 16.4 traffic, taken \
with tcpdump on the database host while a scripted fulfilment workload ran \
across 48 connections, and the cluster was then shot with an immediate \
shutdown while sessions were still holding transactions open. The graded \
answer is the dump of that cluster after it was restarted and ran crash \
recovery, so the ground truth was produced by postgres itself and not by any \
model of it.
\
Nothing is withheld. The capture carries both directions in full with no \
kernel drops, the baseline dump is the exact state before the window opened, \
and the decoder that reads the pcap and prints the version 3 protocol ships in \
the box, so no time goes on tcp reassembly. A postgres 16.4 cluster is \
installed and startable, so any question about semantics can be settled by \
experiment. What is left is the actual work.
\
The obvious approach is to restore the baseline and replay the traffic. It \
does not work, and that is the point. The capture is one execution and a \
replay is a different one: which session won a race, which one postgres picked \
off as the deadlock victim, which rows SKIP LOCKED handed to whom, whether a \
conditional update still matched by the time it got its lock. 2095 statements \
were issued and the answers on the wire are the only record of what those came \
to. Reading them is the job.
\
Measured on this capture by disabling one reading at a time and comparing \
against the recovered dump. Applying every transaction rather than only the \
committed ones moves 160 rows. Deciding a commit from the sql the client sent \
rather than the tag the server answered with moves 44 rows and 24 verdicts, \
because postgres answers COMMIT on a poisoned transaction with the tag \
ROLLBACK and 24 blocks in here did exactly that. Keeping the statements a \
pipelined batch discarded after its first error moves 40 rows. Treating the \
six transactions still open at the kill as committed moves 28 rows and 8 \
verdicts. Ignoring rollback to savepoint moves 18 rows, and there are nested \
savepoints where the outer rollback has to take the inner work with it. \
Treating each part of a multi statement simple query as standing on its own \
moves 16 rows, because outside a transaction block those parts are one \
implicit transaction and a duplicate key part way down takes back the \
statements that already answered with a row count. Reading the upsert as \
insert or ignore moves 12 rows. Ignoring the row counts moves 8. Grading is \
all or nothing over 676 rows and 335 verdicts, so any one of those is a zero.
\
For a person this is a long careful day: decode, pair every statement with the \
answer it got, get the transaction bookkeeping right, model what each \
statement did from its own evidence, and hold all of it together over 48 \
connections. There is no partial credit and no way to sample your way to \
confidence, because the one thing you cannot check locally is the answer.
"""
solution_explanation = """
Read the capture with the shipped decoder and pair every statement with the \
answer it got. That pairing is the first real hurdle. A simple query message \
can carry several statements and answers with one CommandComplete each, and a \
pipelined batch behind one sync stops dead at its first error with everything \
after it discarded unread, so anything still outstanding when ReadyForQuery \
arrives never ran.
\
Then the transaction bookkeeping. A block committed only if the server answered \
its COMMIT with the tag COMMIT; a block that had already hit an error answers \
ROLLBACK to the same request. Rollback to savepoint discards the effects back \
to that mark and a rollback to an outer savepoint takes the inner ones with \
it. Anything still open when the capture stops was rolled back by recovery. \
Statements outside any block are their own transaction, except that the parts \
of one multi statement simple query are a single implicit transaction and fail \
together.
\
What each surviving statement did is then read off its own answer rather than \
recomputed. The row count says whether a conditional update matched. A \
RETURNING row gives the value the row actually took, which is what settles the \
upsert, since ON CONFLICT DO UPDATE reports INSERT 0 1 whether it inserted or \
updated. Effects are applied in the order their answers came back, which is \
sound because two statements touching the same row are serialised by its lock, \
so the second cannot answer before the first transaction ends.
\
solution/derive.py does exactly that and then writes the surviving effects into \
a live postgres 16.4 restored from the baseline dump with psql, and reads the \
four tables back out of it. Asserted at build time to reproduce the recovered \
dump row for row, and its verdicts are checked against what the workload driver \
itself saw on all 329 blocks the driver settled.
"""
verification_explanation = """
The agent leaves /app/state.json and the verifier compares it with the dump \
taken from the cluster after it was restarted and ran crash recovery. That \
dump, and the verdict for all 335 transaction blocks, live only in the verifier \
image under /tests/sealed, root owned and mode 0700. Nothing about the answer \
is present in the agent container: it holds the capture, the baseline dump, a \
decoder and an empty postgres, and the state at the kill is not derivable from \
any of them without doing the work.
\
Each of the four tables is normalised and compared as a set of rows, so row \
order is free while every row and every column must be exact, and duplicate \
rows are rejected. Numeric columns are compared as integers so a quoted figure \
is accepted, text columns as text, nulls never. The verdict map has to name \
every block in the capture and no others, and each value has to be commit or \
abort. Any extra key in the file is a fail.
\
Reward is one only when all five checks pass and zero otherwise, written on \
every path including a missing file, unparseable json, wrong shapes and a crash \
inside pytest, because test.sh writes zero before pytest starts and only \
overwrites it on a clean exit.
\
Measured here: the reference scores one, doing nothing scores zero, and six \
cheat attempts score zero, among them the baseline copied over unchanged, a \
replay of the traffic into a real postgres in wire order, one that applies \
every statement in the capture regardless of outcome, one that calls every \
block a commit, and one that fabricates a well formed file of plausible rows.
"""
category = "Software"
subcategory = "Databases"
tags = ["postgres", "packet-capture", "wire-protocol", "transactions",
        "incident-forensics", "crash-recovery"]
expert_time_estimate_hours = 9
relevant_experience = """
Most of my database work has been on the operations side, which means I have \
spent more evenings than I would like reconstructing what a server did from \
whatever was still lying around after it stopped doing it. Logs that stop \
mid-sentence, an application that only records what it meant to do, and a \
finance team who need a number by Friday.
\
A packet capture is the best of a bad set of options, and the reason is that \
it records the answers. An application log tells you what was sent. The wire \
tells you what came back, and what came back is the only thing that knows \
whether the update matched a row, whether the commit was really a commit, and \
whether the statement ran at all. The habit that took me longest to learn is \
that you never rerun the traffic to find out. I have watched people restore a \
backup, replay a day of statements and present the result, and it is always \
close and always wrong, because the interesting statements are the contended \
ones and those are exactly the ones a replay decides differently.
\
The other thing this job teaches is respect for the protocol's small print. \
Which statements a batch throws away after an error, what a multi statement \
query does when one part of it fails, what tag comes back when you commit a \
transaction that is already dead. None of that is obscure to postgres. It is \
just that most people never have to care, and then one night they do.
"""

[verifier]
timeout_sec = 900.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 2400.0
cpus = 4
memory_mb = 4096
storage_mb = 20480
gpus = 0
```

## instruction.md
```markdown
We lost the fulfilment primary on Tuesday night. Postgres 16.4, immediate
shutdown, nothing graceful about it. The box came back long enough to start the
server once, which meant it ran crash recovery, and then the array failed for
good and took the cluster with it. So there is no database left to ask. What
survived is a packet capture, because tcpdump has been running on that host
since the last incident and it was writing to a different disk.

That capture is `/app/incident/capture.pcap`. Classic libpcap file, both
directions, every client connection on port 5432, from the moment the tap went
on to the moment the server stopped answering. Nothing was dropped by the
kernel while it ran, so what is in there is all of it and all of it is in there.

Finance are reconciling against the warehouse and they want the tables as they
actually stood at the end. Not roughly. One order either way turns into a
fortnight of email.

Here is what you have. `/app/incident/baseline.sql` is a `pg_dump` taken a few
seconds before the tap went on, with nothing else connected at the time, so it
is exactly what those tables held before any of the captured traffic ran. Four
tables in it. `stock` is `sku, qty, reserved`. `orders` is
`id, cust, status, cents`. `lines` is `order_id, sku, qty`. `audit` is
`seq, actor, note`. No triggers, no defaults, no sequences, and every value the
app writes it either sends or reads back, which is the only reason this job is
possible at all.

There is a postgres 16.4 cluster in the box too. `/app/pg/start.sh` brings it
up, it is empty, and it is yours to do whatever you like with. `psql`,
`pg_dump` and the rest of the 16.4 client tools are on the path, and
`psycopg 3.2.3` is installed if you would rather drive it from python. No
network, so whatever you want has to be in there already.

I have already written the tedious part. `/app/tools/pgcap.py` reads the pcap,
reassembles the tcp, and prints the version 3 frontend and backend protocol as
one json object per message: `python3 /app/tools/pgcap.py <file>` for the lot,
`--conn N` for one connection, `--summary` for a list. It numbers connections
from 1 in the order they open in the capture and those numbers matter below.
Every message carries `t`, seconds from the first packet in the file. Do not
spend your afternoon writing another one of these.

What I want is `/app/state.json`. Five keys.

`stock`, `orders`, `lines` and `audit` are each a list of rows, one row per
row in that table when the server stopped, and a row is a list of its columns in
the order I gave above. Row order in the list does not matter. The contents do,
exactly, every row and every column.

The fifth key is `txns` and it is an object. One entry per transaction block in
the capture, keyed `"C:N"` where C is the connection number pgcap gives that
connection and N counts the `BEGIN` statements on it starting at 1. The value is
`"commit"` if that block committed and `"abort"` if it did not, and there is no
third answer. Every `BEGIN` gets an entry including any that were still open
when the server went down. Statements sent with no `BEGIN` around them are not
transaction blocks, so they get no entry and do not shift the numbering.

Two things about the material that will save you time. The state I want is the
state after recovery, which is what the server would have served had the disks
held, and that is what finance are comparing against. And nothing was sitting in
the middle of a `COMMIT` when it died. Every session that asked for one got its
answer while the tap was still running, so there is nothing in doubt and nothing
you have to guess at. Everything else that happened in that window is in the
capture and can be settled from it.

Grading is the whole thing at once. Four tables and every transaction verdict.
One row wrong, one verdict wrong, and it is a no.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
