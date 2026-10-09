# kv-batch-plan

## task.toml
```toml
artifacts = ["/app/schedule.json"]

[task]
name = "afterquery/kv-batch-plan"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "This is the offline batch scheduling an inference serving engineer does when draining a queue of requests through one continuous-batching replica, packing them into the fewest sequential decode waves under the PagedAttention KV-cache block budget and the max concurrent sequences the engine admits. The packing itself is a bounded two-constraint bin packing a solver handles. The hard part is that the instance the solver runs on is not given cleanly: each request's true peak KV footprint, ceil of its total token length over the paged block size, has to be reconstructed by crossing several signals in the raw gateway log, and the obvious single-field read is confidently wrong. The prompt token count is neither the log's est_tokens field, a chars-over-four heuristic, nor the tokenizer count of the stored prompt on its own, because the served model wraps every prompt in the chat template recorded in the engine config, so the real prompt length only follows from tokenizing the templated prompt with the model's own tokenizer shipped in the environment. The generated token count is not the requested max_tokens, because generation stopped early wherever the finish reason is stop, so the true decode length is the tokenizer count of the recorded response text, and a whitespace word count of that response undercounts the sub-word tokens. The block size is the value the running replica loaded from the engine config, not the stale value left in a superseded profile file. A handful of entries are retried duplicate submissions the gateway collapsed to a single run, so counting both inflates a wave. Each of these is load bearing and they couple through the two per-wave limits, so a single wrong prompt length, a decode length taken from the cap, a footprint sized with the stale block size, or a double-counted retry either overfills a wave beyond the real KV budget or spends more waves than the true minimum. The shipped requests.jsonl, engine_config.json, the stale profile and the vendored tokenizer.json are generated deterministically to mirror what such a serving stack produces, and the sealed true footprints and minimum live only in the verifier."
solution_explanation = "Reconstruct each request's true KV footprint from the agent-visible files, then pack. For every entry in /app/requests.jsonl drop the retries the gateway collapsed, identified by their retry marker pointing at an original with identical content, keeping the original once. For each surviving request compute true prompt tokens by applying the chat template from /app/engine_config.json to the stored prompt and tokenizing the result with /app/tokenizer.json, ignoring the est_tokens field; compute true decode tokens by tokenizing the recorded response text, which equals max_tokens only where the finish reason is length and is shorter wherever it is stop; take the block size from the engine config, not the superseded profile; and set the footprint to ceil of the summed prompt and decode tokens over the block size. With the true footprints, the max_num_seqs cap and the num_gpu_blocks budget from the engine config, minimise the number of waves so that each wave holds at most max_num_seqs requests and its summed blocks fit num_gpu_blocks, solved exactly with OR-Tools CP-SAT. The reference rebuilds the instance from the agent-visible files alone and reproduces the sealed minimum of 6 waves over 30 runnable requests, writing the ordered waves to /app/schedule.json."
verification_explanation = "The deliverable is data and the verifier runs nothing the agent wrote. It loads /app/schedule.json, requires an object whose waves key is an ordered list of lists of request ids, checks that the union of the waves is exactly the sealed set of runnable requests with each id appearing in exactly one wave and no extra or missing id, then checks feasibility against the sealed true footprints: every wave holds at most max_num_seqs requests and its summed KV blocks are at most num_gpu_blocks. It then requires the number of waves to equal the true minimum, which it recomputes from the sealed footprints with OR-Tools CP-SAT rather than trusting a stored constant and cross-checks against the baked minimum of 6. Grading is all or nothing and two sided, so a feasible but non-minimal schedule and an infeasible schedule both score 0. The true per-request blocks, the two caps and the optimum are baked into the verifier image and absent from the agent container, and the entrypoint writes a 0 or 1 reward plus a CTRF report on every path including a crash or a missing artifact."
category = "ML"
subcategory = "Inference"
tags = ["inference-serving", "continuous-batching", "paged-attention", "scheduling", "reconstruction"]
expert_time_estimate_hours = 8
relevant_experience = "I have run offline batch scheduling against continuous-batching LLM serving stacks, sizing requests by their true paged-attention KV footprint from gateway request and response logs, accounting for the served model's chat template, early stopping versus the requested token cap, tokenizer sub-word counts, stale engine configuration, and de-duplicated retries, then packing the batch under the KV block budget and the concurrent sequence limit as an integer program."

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
we've got a backlog of inference requests queued for one model replica and i need them scheduled through it in as few decode waves as possible. the replica runs continuous batching over a paged kv cache, so a wave is just the set of requests that sit resident together and decode alongside each other, and the batch drains wave by wave until it's empty. fewer waves clears the backlog sooner and that is the whole point.

the queued work is in `/app/requests.jsonl`, one json object per line straight off the gateway: the request id, the prompt text, a couple of logged size fields, the requested max_tokens, and the recorded response text with its finish reason. the replica's paging parameters live in `/app/engine_config.json`, the block size, the number of gpu kv blocks the cache holds, the max concurrent sequences it will admit, and the chat template the served model wraps every prompt in. the served model's tokenizer is `/app/tokenizer.json`.

here is what a wave has to respect. while a request is resident it holds kv cache in fixed size blocks, ceil of its total token length over the block size, and total length is the prompt the server actually feeds the model plus everything the request generated. a wave holds at most max_num_seqs requests, and the blocks held by the requests in a wave have to fit inside num_gpu_blocks. two limits per wave, nothing else.

write the plan to `/app/schedule.json`, one object with a single key `waves` mapping to an ordered list of waves, each wave a list of the request ids that run in it, like `{"waves": [["req-004","req-011"], ["req-000"], ...]}`. every request that runs appears in exactly one wave and nothing that did not run appears at all.

a word on the log. it is the raw gateway feed, not a clean work order. a few of the columns are estimates or the ceiling the caller asked for rather than what the request actually did, and some entries are retries the gateway collapses back to a single run. so do not size a request off one column and do not count a collapsed retry twice, reconstruct what each request truly put through the model before you pack it.

grading is all or nothing. the schedule is scored against the true footprints: it must cover exactly the requests that really ran, once each, every wave has to be feasible on the real block budget and the real sequence cap, and the number of waves has to equal the true minimum. a feasible plan that spends more waves than the minimum fails, and so does a plan that looks tight because it trusted a number that was not the real footprint.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
