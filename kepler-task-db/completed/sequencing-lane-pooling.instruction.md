we have a sequencing queue to clear for the 2026-09-21 plan date and i want the run plan for it done the way lp-7 says, not by feel. everything is under `/app`. read `/app/SOP.md` first, it is our standing procedure and it defines every rule the plan is held to. `/app/README.md` lists the rest of the drop: the lims export, the project contracts, the kit manifests, the instrument's run history, and the sample sheets plus bcl convert reports of the recent runs.

the job. decide how many novaseq flowcells we buy, which type and read recipe each one runs, and which lane every library in the queue goes into. total price at the minimum. every library that qualifies placed once. lanes that would actually demultiplex and actually fit.

the drop is what our systems emitted, not a clean problem statement. lims rows, vendor manifests, contracts and the run record do not all agree, and the sop says which one wins where they differ. the real index each library carries, what each one still needs, and what a lane of each flowcell type can really take all have to come out of those files.

write the plan to `/app/plan`. `/app/plan/runs.csv` with the columns `run_id,flowcell`, one row per flowcell you buy. then for every run_id a directory `/app/plan/<run_id>/` holding `SampleSheet.csv` in sample sheet v2 form: a `[Reads]` section with `Read1Cycles`, `Read2Cycles`, `Index1Cycles`, `Index2Cycles`, and a `[BCLConvert_Data]` section with the columns `Lane`, `Sample_ID`, `Index`, `Index2`, one row per library, exactly as section 7 of the sop spells out. `Sample_ID` is the `library_id`. `Index2` as our instrument reads it.

it is scored all or nothing on the real requirements, real indices and real yields, and only the lowest total price passes. a cheaper looking plan built on a wrong reading of the drop will not fit or will not demultiplex. a safe plan with a spare flowcell is above the minimum. neither counts.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
