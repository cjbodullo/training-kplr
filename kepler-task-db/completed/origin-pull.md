# origin-pull (Software/Systems, $300) v2 — built+local-green, HELD 2026-09-15

## task.toml
```toml
artifacts = ["/app/egress.json"]

[task]
name = "afterquery/origin-pull"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "This is the origin bandwidth true-up a CDN or platform capacity engineer runs when the only surviving record of a busy period is the edge access log and the origin side is gone. The task is the exact origin egress, in body bytes, per origin per window, across three origins and six windows, so eighteen cells that all have to be right. It is hard first because the client access log is a confidently misleading proxy for origin traffic and it is wrong in both directions at once. Concurrent misses for one object collapse onto a single origin pull while the log still shows one line per client, so summing client bytes over-counts. A request served stale inside a grace window is logged as a cache hit yet it triggers a real revalidation to the origin that appears nowhere in the log as a fetch, so trusting the HIT marks under-counts, and when the object carries no validator that background refresh pulls the whole body rather than a not-modified with no body. Range responses show a small partial to the client while the edge pulled the full object. It is hard second because nobody hands over the cache behaviour: the policy states only what to count and how to place a pull in a window, and the engineer has to supply how the edge actually pulls from origin. The real cache parameters live in the deployed vcl, not in the object manifest, whose ttl and grace columns have drifted from what was running, so an engineer who trusts the manifest is wrong on several objects. The vcl also normalizes the cache key by dropping the query string, so cache-busting variants of one url are a single object rather than many pulls, and it passes an endpoint uncached, so every request there is its own origin pull; both are only visible by reading the vcl. A ban forces a pull of an object that by age looks fine. None of this is visible as an origin fetch in the log; the engineer runs the edge object state machine forward per cache key, deciding for each request whether it was a hit, a stale serve that spun off one revalidation, or a real miss others coalesced onto, then places each pull in the right window. There is no origin log to check against and the tier is torn down, so no candidate figure can be verified by re-running anything. For a person it is a careful reconstruction over roughly a hundred and twenty requests and sixteen objects on three origins, exact to the byte across eighteen cells, where one mis-classified request throws a cell and nothing flags it. The shipped access log is synthetic but was produced by a real Varnish 7.1 tier running the shipped vcl, with real request coalescing, grace revalidation, conditional not-modified refreshes, cache-key normalization, an uncached pass route, range, and two real bans; the origin egress it is graded against was measured from that tier's own backend logs."
solution_explanation = "Parse the varnishncsa access log into per-request rows with a microsecond timestamp, host, normalized path (drop the query string, the deployed vcl hashes without it), status, client bytes and the hit or miss marker. Take each object's real ttl and grace from the deployed cache.vcl, not from assets.tsv whose ttl and grace have drifted; read the object's origin, body size, validator and origin response time from the manifest, and read the vcl's pass rule and key normalization. Then simulate the edge object state machine per cache key over the requests in time order, tracking when the stored copy was last refreshed, whether a foreground miss pull is in flight, and whether an asynchronous revalidation is in flight. For each request compute the age from the last refresh completion: inside ttl it is a free hit; inside grace it is served stale and, unless a revalidation is already running for that key, it starts exactly one revalidation whose origin cost is zero body bytes when the object has a validator and the full body otherwise; past grace or with no grace it is a miss that pulls the full body, and concurrent requests within that pull's in-flight window coalesce onto it. A request to the uncached pass route is always a full pull. A banned object takes a forced full pull on its first request after the ban time. A range request that needs a pull still pulls the full object. Attribute each pull's body bytes to the window holding the client request that caused it and sum per origin. The reference reproduces the sealed figures, which run from 0 up to 363000 across the eighteen cells. Every shortcut misses: summing all client bytes over-counts, summing only MISS-line bytes under-counts, counting one pull per logged miss is wrong, and trusting the manifest's drifted ttl and grace is wrong on three objects."
verification_explanation = "The deliverable is data, so the verifier runs nothing the agent produced and needs no cache tooling. It json.loads /app/egress.json, checks it is an object whose keys are exactly the three origin names, each mapping to exactly the six window names with non-negative integer values, then compares every one of the eighteen cells against a sealed answer.json baked into the verifier image and never present in the agent container. Grading is one exact set of integers over all eighteen cells; a value wrong in either direction fails, so over-counting and under-counting fail identically and there is no partial credit. The sealed answer was produced by the reference reconstruction over the shipped log and cross-checked against the true origin egress measured from the real backend logs of the Varnish run that produced the log, and every naive baseline was verified to miss it. The verifier runs in its own separate container after the agent container is torn down, the answer file is unreadable from the agent image, and reward.txt is written on every code path including a crash."
category = "Software"
subcategory = "Systems"
tags = ["cdn", "varnish", "cache", "http", "capacity", "forensics"]
expert_time_estimate_hours = 5
relevant_experience = "I have run edge caching and origin capacity for high traffic sites on Varnish and CDN tiers, and had to answer exactly this question during incident and billing reconciliation: given only the edge access log, what did each origin actually serve. That means reading varnishncsa output against the running VCL, accounting for request coalescing on the waiting list, grace mode stale-while-revalidate, conditional revalidation returning 304 with no body, range fetches that pull the full object, and ban invalidation, and separating origin egress from client egress rather than trusting the HIT and MISS markers."

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
i have the edge access log from our cache tier for a two minute window and i need the origin bandwidth out of it. the bytes each of the three origins actually served, per origin per window. not what the edge sent to viewers, the two are not the same number and that is the whole problem.

everything is under `/app`. `/app/access_log` is the varnishncsa client log, one line per viewer request: a timestamp, the host, the request line, the status, the bytes the edge sent that client, and a HIT or MISS marker. `/app/cache.vcl` is the vcl that was deployed on the tier during the capture, read it, it is what actually ran. `/app/assets.tsv` is the origin object manifest with each object's origin, body size, validator and origin response time, plus the ttl and grace it was designed with, some of which have drifted from what the vcl deployed. read `/app/POLICY.md` first, it is CEP-1, it pins down what counts as origin egress, which record wins when they disagree, the six windows, and the two bans that ran. it will not tell you which requests went to origin, that comes from the config and how the tier behaves.

write `/app/egress.json`, one object keyed by origin then by window, origin egress in body bytes:

    {"img":    {"W1":0,"W2":0,"W3":0,"W4":0,"W5":0,"W6":0},
     "api":    {"W1":0,"W2":0,"W3":0,"W4":0,"W5":0,"W6":0},
     "assets": {"W1":0,"W2":0,"W3":0,"W4":0,"W5":0,"W6":0}}

all three origins, all six windows, integer bytes. graded exact against the figures i cut by hand, all or nothing, every one of the eighteen cells has to land. a cell too high and a cell too low are the same miss, so there is no rounding you can hide behind. the log is the only record of the traffic that survived. there is no origin side log in the box and the tier itself is gone, so the numbers come from reading the log against the deployed config and nothing in the box will confirm a cell for you.

nothing else you leave in `/app` is kept. only `/app/egress.json` comes back.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
