# compaction-plan

## task.toml
```toml
artifacts = ["/app/plan.json"]

[task]
name = "afterquery/compaction-plan"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "This is the small-file compaction pass a data or platform engineer plans before running a rewrite on an Apache Iceberg lake table that has drifted into many tiny files across a few partitions. The shipped table is a real Iceberg v2 (merge-on-read) table on local disk: a metadata.json, avro manifests and a manifest list, parquet data files partitioned by region, positional delete files, and a handful of dead data files that a prior compaction replaced but that still sit in the warehouse directory. The compaction itself is a bounded bin packing that a solver handles instantly. The difficulty is that the instance the solver must run on is not readable from any single place in the table, and four separate facts about each file have to be crossed from disagreeing sources, with the obvious single read confidently wrong. The set of files to compact is not a directory listing, because the warehouse still holds the files an earlier compaction commit dropped, so the live set only follows from the current snapshot's data manifests. A file's live row count is not the manifest record_count, which is the pre-delete original, because the positional delete files remove rows that only that file's delete entries reveal, and a file whose rows are entirely deleted has fallen to zero live rows and must leave the plan rather than waste an output slot. The size a file will contribute after merging is not its on-disk file_size_in_bytes, because narrow compressed rows on disk understate the logical merged size, which is the live row count times the table's recorded average bytes per row; sizing a group by summed input bytes silently packs groups that overflow the real output ceiling. And a file's partition is not always the region value carried in its row data, because one file's column stat disagrees with the authoritative manifest partition tuple, and grouping it by the data value crosses a real partition boundary. Each of these is load bearing and the constraints couple them, so a single wrong live set, a trusted record_count, a kept empty file, a byte size read for capacity, or a mislabelled partition yields a plan that looks clean on the believed numbers and either covers the wrong files, overflows a real output file, mixes partitions, or spends more output files than the true minimum. There is no local check; the true instance lives only in the grader. The table has three partitions with roughly a dozen live files, tuned so the minimum output-file count binds, and the metadata, manifests, delete files and stats are generated deterministically to mirror what such a table produces."
solution_explanation = "Rebuild the true instance from the table, then pack it. Read the current snapshot's data manifest entries to get the live data files, which excludes the dead files still on disk. For each live file, take its manifest record_count and subtract the rows removed by the positional delete files that target its path, giving the true live row count, and drop any file whose live count is zero. Compute each file's true output contribution as live rows times the table property compaction.avg-row-bytes, ignoring the on-disk file_size_in_bytes. Take each file's partition from the manifest partition tuple, not from the region value in the row data, so the one mislabelled file stays in its true partition. With the true live files, partitions and output sizes in hand, solve per partition for the minimum number of output files: a classic one dimensional bin packing where items are the files' output byte contributions and each bin is capped at compaction.max-output-bytes, solved exactly with OR-Tools CP-SAT, and the plan is the union of the per-partition packings. The reference reconstructs the instance from the agent-visible table alone and reproduces the sealed minimum of 7 output files."
verification_explanation = "The deliverable is data and the verifier runs nothing the agent wrote. It loads /app/plan.json, requires an object whose groups value is a list of non-empty lists of file ids, and grades it against the sealed truth baked into the verifier image: the true live-and-nonempty data files, each with its true partition, live row count and output byte size, plus the size ceiling. It checks that the flattened ids are exactly the true live-nonempty file set with no missing file, no dead or fully-deleted extra, and no duplicate; that every group's files share one true partition; that every group's summed true output size is within the ceiling; and that the number of groups equals the minimum, which it recomputes per partition from the sealed sizes with OR-Tools CP-SAT rather than trusting a stored number, cross-checking the baked optimum. Grading is all or nothing and two sided, so a feasible but non-minimal plan and an infeasible plan both score 0. The true per-file sizes, partitions, live set and optimum are baked into the verifier image and absent from the agent container, the reward directory is root owned, and a 0 or 1 reward plus a CTRF report are written on every path including a crash."
category = "Software"
subcategory = "Data engineering"
tags = ["iceberg", "data-engineering", "compaction", "data-reconciliation", "constraint-solving"]
expert_time_estimate_hours = 8
relevant_experience = "I have run and planned small-file compaction on Apache Iceberg lake tables, reading the current snapshot through its manifests and manifest list, applying positional and equality delete files to recover live row counts, distinguishing live data files from the dead files a prior rewrite left in the warehouse, and sizing merged outputs from logical row widths rather than on-disk bytes, then modelling the rewrite as a per-partition bin packing under an output size target."

[verifier]
timeout_sec = 300.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 1200.0
cpus = 4
memory_mb = 4096
storage_mb = 10240
gpus = 0
```

## instruction.md
```
one of our lake tables has drifted into thousands of tiny files in a few partitions and reads are paying for it. i need the next compaction pass planned, and planned tight, before we run the rewrite. this is the plan step only, you are not rewriting any data, you are telling me which input files get merged together.

the table sits at `/app/warehouse`, an iceberg table under namespace `db`, table `t`, with the sqlite catalog at `/app/warehouse/catalog.db` and the table tree at `/app/warehouse/db/t`. it is a v2 table so alongside the `.parquet` data files there are positional delete files and the usual avro manifests and manifest list. partitioning is by `region`.

what i want back is `/app/plan.json`, a single object with one key `groups`, whose value is a list of groups, each group a non empty list of file ids. a file id is the base name of a data file, like `data-0007.parquet`. so `{"groups": [["data-0001.parquet","data-0003.parquet"], ["data-0002.parquet"]]}`. nothing else in the file. each group is one output file the rewrite will produce by merging exactly the inputs you list.

the plan has to be a partition of the table's live, non empty data files. every data file that is live in the current snapshot and still has at least one row after deletes must appear in exactly one group. a file that is not part of the current snapshot is not yours to compact, and a file whose rows are all gone once deletes are applied is not compacted either, it just gets dropped, so it must not appear anywhere. do not invent ids, do not repeat an id across groups, do not leave a live file out.

the rules a group has to obey. compaction is per partition, so two files that live in different `region` partitions can never share a group. and a group cannot be bigger than one output file is allowed to be. an output file's size is its total live row count times the average bytes per row, which is recorded on the table as the property `compaction.avg-row-bytes`, and the ceiling is the property `compaction.max-output-bytes`, which is 134217728 bytes. so for every group, the sum over its files of live rows times avg bytes per row must be at most that ceiling.

now the objective. i want the fewest output files, meaning the fewest groups, that covers every live non empty file while obeying the partition rule and the size ceiling. cheapest read amplification is fewest files, so minimise the group count. i mean the real minimum, not merely something that fits.

the catch, and why i am not just firing off the rewrite blind, is that the true state of this table does not read cleanly off any one place, and the obvious single read is wrong more than once here. so do not take any one number at face value. reconcile what is actually live and how big each file really compacts to before you pack anything. i have seen plenty of compaction plans that looked fine on paper and then rewrote the wrong set.

grading is all or nothing against the true state of the table. the plan must cover exactly the live non empty files, every group must sit in a single partition and stay within the size ceiling on the true live sizes, and the group count must equal the true minimum. a plan that is feasible but uses more groups than the minimum fails, and so does one that looks small because it trusted a count or a size that was not the live truth.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
