# proto-cover — archived manifest (built 2026-09-15, HELD)

## task.toml
```toml
artifacts = ["/app/blocking.json"]

[task]
name = "afterquery/proto-cover"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "This is the review a platform engineer runs before a protobuf schema change ships to a gRPC surface that other teams still read on the old schema. For each proposed change to the fleet.v1 messages the board must decide, under the house release-safety policy RSP-7, whether the change is release-blocking. It is hard because none of the three conditions the policy turns on can be read off a label. The changelog is the authoring team's own prose and it is wrong in both directions: it calls a field-number reuse a rename, calls a field that is still on the wire unused, and claims coverage that is not there. So the wire hazard has to be established from the two .proto files themselves, decoded field number by field number with real protoc descriptors, and crossed with whether that field is actually populated in the captured production wire, since a change to a field no producer sets is not a hazard and a captured stream only tells you which numbers are live if you decode it. Exposure is a second reconstruction: a hazard blocks only if a reader still pinned to the old schema will receive the message, and that reader is three joins away, service to rpc id to message name through an alias, then service to instance, then instance to the active set, with a pinned instance that has been drained sitting there as a trap. The third condition is shim coverage, where a migration entry counts only if it names the exact message and the exact baseline field number and is already effective, and the shipped list includes one aimed at the wrong number and one that only takes effect next release. Both over-inclusion and under-inclusion fail, so trusting the changelog, or flagging every wire-incompatible change the way an off-the-shelf breaking-change checker would, both miss. For an experienced engineer this is a careful day of work across the schemas, the captures and the deploy topology; the captures are synthetic production samples built for this task, so nothing here is online, and the policy is house-specific rather than the textbook wire-compatibility rules."
solution_explanation = "Work the policy RSP-7 as a three-way conjunction and derive every input from the artifacts, never the changelog. First build the field maps: compile schema/baseline/fleet.proto and schema/proposal/fleet.proto to descriptor sets with the real protoc and read, per message, each field number's wire group (varint, zigzag, 32-bit, 64-bit, length-delimited), whether it is repeated, and its packed flag. Second, get liveness by decoding captures/<Message>.bin generically: it is a length-delimited frame stream, and scanning tags gives the set of field numbers that actually appear, which is all the policy needs. A change is a wire hazard on a live field when the baseline number is present in the captures and either the field is gone in the proposal (deletion), its wire group differs (a cross-group type change, which is how a genuine number reuse shows up), or a repeated scalar numeric flips packed. Same-group retypes, renames, additions at fresh numbers, string to bytes, and any change to a dead field are not hazards. Third, exposure: resolve the consumers of the message through service_graph.json (service to consumed rpc ids, rpc id to message via the catalog and aliases), then check deploy/instances.json for an instance of a consumer whose schema_track is baseline and whose id is in deploy/active.txt; a drained pinned instance does not count. Fourth, coverage: a shim in deploy/migrations.json counts only if its message and field_number match the touched baseline number exactly and effective_release is at most RELEASE.txt. A change is blocking exactly when it is a live wire hazard, exposed to an active pinned reader, and uncovered. Writing /app/blocking.json is then a filter over the change list. The traps are two-sided: dead-field hazards, hazards on messages with no active pinned consumer, and validly shimmed hazards are all non-blocking, while a reuse the changelog calls a rename, a live delete it calls unused, a packed flip an off-the-shelf checker treats as safe, and hazards whose only shim is misaimed or not yet effective are all blocking."
verification_explanation = "The deliverable is data and the verifier runs nothing the agent wrote. It loads /app/blocking.json, requires a json object with a 'blocking' list of known change ids with no duplicates and no unknown ids, and compares that set to the sealed release-blocking set baked into the verifier image under /tests. The comparison is exact and two-sided: any missing id or any extra id fails, and grading is all or nothing over the change set, so a set that is admitted-looking but includes a non-blocking change scores zero, as does one that misses a blocking change. The sealed set was produced at build time by a policy engine over the authoring model and is independently reproduced by the reference solution, which recomputes it from the shipped artifacts alone using the real protobuf toolchain, so the answer is derivable rather than planted. The verifier image is separate, the sealed set is never present in the agent container, the reward directory is root owned, and a 0 or 1 reward is written on every path including a crash."
category = "Software"
subcategory = "Systems"
tags = ["protobuf", "grpc", "schema-evolution", "wire-compatibility", "release-engineering"]
expert_time_estimate_hours = 6
relevant_experience = "I have run schema governance for a gRPC service surface with many independent consumers, including the release review that decides whether a proposed protobuf change is safe to ship while some readers are still pinned to the previous schema. That work is exactly this: reconciling the .proto diff against what is actually on the wire in captured traffic, tracing which consumers a message reaches through the service graph and the deployment topology, and deciding case by case against a house compatibility policy rather than the generic wire-compatibility rules, where the authoring notes and the migration records cannot be taken at face value."

[verifier]
timeout_sec = 120.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 1800.0
cpus = 2
memory_mb = 2048
storage_mb = 10240
gpus = 0
```

## instruction.md
```
we are cutting release 48 of the ridgeline fleet.v1 grpc schema and i need the release review done before it ships. some services in the fleet still read the old schema, so a change that looks clean in the .proto can still break a reader that never moved. the board does not eyeball this. we decide it with our own policy, RSP-7, written out in /app/POLICY.md. read that first. it is the contract, not me.

everything is under /app. schema/baseline/fleet.proto is deployed today. schema/proposal/fleet.proto is what we want to ship. /app/changes.json lists every proposed change, one id each, with the field it touches and a note from whoever wrote it. /app/CHANGELOG.md is those same notes as prose. the notes are not authoritative and some of them are just wrong. what decides a change is the two .proto files, the captured production wire under /app/captures, and the deploy records under /app/deploy and /app/service_graph.json. where a note disagrees with the artifacts, the artifacts win. POLICY.md says exactly this and spells out how each of the three conditions is judged. RELEASE.txt holds the release number under cut.

i want back the set of changes that are release-blocking for release 48 under RSP-7. write it to /app/blocking.json. one json object, a single key "blocking", whose value is a list of the change ids that block. every blocking id, and nothing that does not block. a blocking id left out is wrong and a non blocking id put in is wrong, so it is all or nothing. the ids are the ones from /app/changes.json. nothing outside /app matters.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
