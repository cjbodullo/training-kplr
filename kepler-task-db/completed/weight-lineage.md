# weight-lineage — completed bundle manifest

## task.toml
```toml
artifacts = ["/app/findings.json"]

[task]
name = "afterquery/weight-lineage"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "This is the provenance-integrity review an ML platform or model-governance engineer runs on a model hub before a quarter closes, and it is judged on both sides: clear a checkpoint whose record is fine and you have wasted a re-review, but miss one and a model that really descends from a restricted origin ships with a laundered lineage. The corpus is 32 real safetensors checkpoints forming a genuine derivation graph: roots trained from scratch, fine-tunes, and two-parent merges, spread across several generations. What makes it work and not a lookup is that the records lie. The registry's parent attributions and each config's base_model are self-reported and some have been edited to hide or fabricate ancestry, so believing them is wrong in both directions. Only the creation order is trustworthy. The true parentage is carried in the weights, because a fine-tune leaves the tensors it did not train byte-identical to its parent and a merge takes whole tensors from each parent, so the derivation graph has to be reconstructed from which checkpoints share which exact tensors, with creation order fixing direction. That reconstruction is the hard part and it defeats the obvious shortcuts: trusting the registry misses every laundered model, and a nearest-single-parent guess misses a merge whose restricted contribution is the smaller block of tensors, so the restriction it carries is invisible unless both parents of every merge are recovered. Restriction then has to be propagated down the reconstructed graph, and finally each checkpoint is judged on its own record: whether the restricted-derived status implied by the parent it names differs from its true status. A parent that is wrong but leaves that status unchanged is a benign bookkeeping slip and must not be reported, so flagging every discrepancy over-reports. Nothing in the container returns the answer: no tool takes a hub and a policy and yields the set. Grading is an exact set over the 32 checkpoints and one reading in either direction is the whole task. The hub, its registry and the answer are built for this review, so none of it is online. For an expert it is a careful session reading tensors and creation order across the whole graph, and the difficulty is the one the job has, the evidence is in front of you and the disposition of each checkpoint is not."
solution_explanation = "Ignore the registry claimed_parent columns and the config base_model for establishing truth; both are the records under audit and some lie. Load every checkpoint's tensors from its model.safetensors and, for each ordered-earlier pair, count the tensors that are byte-identical. Using registry created_seq for direction, each checkpoint's true parent is the earlier checkpoint it shares the most whole tensors with; when two earlier checkpoints each account for a disjoint block of its tensors it is a merge with both as parents; when nothing earlier shares tensors it is a root. Mark obsidian-base, named by POLICY.md, as the restricted origin and propagate restricted-derived status down this true graph: a checkpoint is restricted-derived if it is the restricted root or any true parent is, and a merge is restricted-derived if either parent is. Then judge each checkpoint on its own recorded parentage: compute the restricted-derived status implied by the parent or parents it names in the registry (using the true restricted-derived status of those named checkpoints, or, if it claims to be trained from scratch, whether it is itself the restricted origin), and report it when that implied status differs from its true status. The materially false set is ten: obsidian-chat and obsidian-lite (fine-tunes of obsidian-sft-v1 that name a clean parent), obsidian-mini (fine-tune of obsidian-code naming a clean parent), fusion-a, fusion-d and fusion-e (merges with a restricted parent that name only the clean one), fusion-g (a merge whose restricted parent is the minority tensor block, so a single-parent guess misses it), edge-deploy (fine-tune of the restricted merge fusion-d naming a clean model), marigold-tiny and marigold-pro (clean models that falsely name a restricted-derived ancestor). The traps that stay off include the honest clean merges fusion-b and fusion-c, and the benign discrepancies cobalt-xl and cobalt-lite, which name the wrong clean parent but stay clean either way."
verification_explanation = "The deliverable is data, so the verifier executes nothing the agent wrote or built and needs no model tooling. It json.loads /app/findings.json, checks it is an object carrying a single tampered list of checkpoint ids that are strings, with no duplicates and every id one of the 32 known checkpoints, and compares that list as a set against a sealed answer baked into the verifier image and never present in the agent container. A missing checkpoint and an extra checkpoint fail identically, so over-reporting and under-reporting both score zero and grading is all or nothing over the 32 checkpoints. The sealed set was produced by the generator that built the corpus and is independently reproduced by the reference, which reads only the material shipped to the agent and inspects the same weights, so the answer is derivable from the evidence alone rather than planted. The verifier runs in its own separate container, the answer file is unreadable from the agent image, the reward directory is root owned and reward.txt is written on every path including a crash."
category = "Software"
subcategory = "Data engineering"
tags = ["model-provenance", "safetensors", "supply-chain", "lineage", "forensics"]
expert_time_estimate_hours = 7
relevant_experience = "I have run the model registry and release side of an ML platform, where provenance is a governance problem and not a formality: knowing which shipped model actually descends from a base whose license or data policy restricts how we deploy it, when a self-reported parent is wrong by accident and when it has been edited to hide a restricted origin, and how a merge quietly carries the most restrictive of its parents. The part that is never a lookup is that the registry is the thing under audit, so the truth has to come from the weights themselves, from which checkpoints share unchanged tensors and in what order they were created, and then be read against what each record claims."

[verifier]
timeout_sec = 120.0
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
our model hub is doing its quarterly provenance audit and the registry can no longer be taken at face value. someone has been editing parent attributions to hide where models really came from. i need the list of checkpoints whose recorded lineage is materially false.

the checkpoints are under `/app/checkpoints`, one dir per checkpoint, each holding a `model.safetensors` with the actual weights and a `config.json`. the provenance registry is `/app/registry.csv`. it has the creation order and each checkpoint's self reported parent (one, or two for a merge). `/app/RELEASE.txt` has context on which columns are trustworthy. the config `base_model` field is self reported too.

read `/app/POLICY.md` first. that is MPG-5, our audit rule. it says which records you can trust, how the true derivation shows up in the weights, which origin is restricted, how the restriction travels, and exactly when a record counts as materially false rather than a harmless mistake. it sets the frame. it does not tell you the disposition of any single checkpoint. you work each one out yourself.

the thing that matters here. a parent claim in the registry is not evidence. the weights are. two checkpoints in a real derive from relation leave a signature in the tensors, and that signature is what settles the true parent, not what the registry or the config says. so a checkpoint can name a clean parent and really descend from the restricted one, or name a scary parent it never came from, and the only way to tell is the weights plus the order things were made in.

write `/app/findings.json`. one object, one key `tampered`, whose value is the list of checkpoint ids (the dir names under `/app/checkpoints`) whose own recorded parentage is materially false under MPG-5:

    {"tampered": ["some-id", "another-id"]}

it is graded as a set against the list i cut by hand, all or nothing. a checkpoint that should be on the list and is left off, and one on the list whose record is actually fine, are the same mistake. order and whitespace do not matter, no duplicates, do not pad it and do not trim it. a wrong parent that does not change whether the model is restricted derived is a bookkeeping slip, not a finding, so do not report it.

nothing else you write is kept. only `/app/findings.json` comes back.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
