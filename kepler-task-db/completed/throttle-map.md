# throttle-map (Software / Systems, $300) — built + hardened + held 2026-09-13

Status: v1 SUBMITTED by user, FAILED reference verification [1,1,0] (latency-fragile oracle); ORACLE HARDENED (server-paced gap measurement), all local gates green + 10/10 robust under injected latency. NOT RESUBMITTED (user submits manually).

## task.toml
```toml
artifacts = ["/app/limits.json"]

[task]
name = "afterquery/throttle-map"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "Reconstructing the rate-limit configuration of a running reverse proxy is work a platform or site reliability engineer does during a migration when the only surviving copy of an nginx gateway is the live box and nobody kept the config. It is hard for a reason that does not go away with effort: a limit_req limit never announces itself, the only signal is which requests come back refused, and the one fact that matters most is invisible to direct observation. Two routes can sit behind one shared counter while carrying different bursts, and two routes can show byte-identical behaviour while sitting behind separate counters, so the observed rate and burst of a route say nothing about whether it shares a counter with any other route. That can only be settled by driving one route's counter to its limit and watching whether another route is refused as a result, and because the counter is shared, probing one route perturbs the state of every route behind the same counter. The evaluation gateway is metered: it serves a fixed number of requests over its whole life and then answers 429 with BUDGET_EXHAUSTED, with no reset and no second instance, so the audit cannot be brute forced by testing every route against every other route and every hypothesis against the box. nginx does not serve its own configuration, and the real server listens only on loopback inside the gateway, so there is no route to read the answer off the machine; it has to be inferred from behaviour alone. A further trap is that the leaky bucket refills with wall-clock time, so a burst counted off a stream of requests spaced by the link's own latency over-reports, because tokens refill between the requests; the count has to be corrected for the time it took, which means the timing of each request matters, not just the tally. Twelve routes have to be resolved at once across three axes, the counter's rate, each route's burst, and which routes share a counter, and grading is an exact set, so one split counter, one merged pair, one burst off by one, or one rate pinned on the wrong route fails the whole thing. The conforming side is as sharp as the nonconforming one: two separate counters with identical settings must be reported as two, and over-reporting sharing fails exactly as under-reporting does. A local nginx is on the box to calibrate a reading against configs the engineer controls, but it cannot disclose the hidden instance's settings. For an expert the bottleneck is designing a probe plan that fits the budget and knowing which coincidences of behaviour have to be cross-checked and which do not, which is the same judgement the task measures."
solution_explanation = "Treat the gateway as a black box reached only through its metered port. For each route, drain its bucket, then send continuously and record the arrival time of every accepted request. A leaky bucket refills with wall-clock time, so simply counting accepts over a latency-spaced stream over-reports; the robust signal is the timing. The first burst+1 requests are admitted back to back, roughly one round-trip apart; once the bucket is full the server only releases one token per 1000/rate ms, so the gap between accepts JUMPS. The count of closely spaced leading accepts is burst+1, and the post-jump gap is the refill period 1000/rate, which is set by the server and so is independent of the link latency; rates of 2 and 5 give 500 ms versus 200 ms gaps, far apart. A route that never returns 503 is unlimited. Then resolve shared counters only among routes of equal rate, the only ones that can share: for a pair, drain both, drive the higher-burst route's counter full, then probe the other route once. A shared counter is now above the other route's lower burst, so its first fresh request is refused; a separate counter is empty, so it is admitted. Each pair is tested in its own drained round so no third route perturbs it, and exhausting the higher-burst side is what makes the single probe decisive. The reference recovers the whole configuration well inside the budget. The insight the task rewards is that equal observed behaviour does not imply a shared counter, and that the burst and rate come from timing the server's own pace rather than from a raw count over a latency-spaced stream."
verification_explanation = "The deliverable is data, so the verifier runs nothing the agent wrote. It reads /app/limits.json, checks the schema (a zones list, each zone an integer rate and a non-empty members list of {route, burst} with burst a non-negative integer, plus an unlimited list of routes), and requires every route in the sealed universe to appear exactly once across all zone members and the unlimited list. It then compares the submission against a sealed answer.json baked into the verifier image: the multiset of zone signatures, where a signature is the rate together with the frozenset of its (route, burst) members, must equal the sealed one, and the set of unlimited routes must equal the sealed one. Two separate counters with identical settings are distinct signatures because their member route sets differ, so a merge or a split changes the multiset and fails. Grading is all or nothing: test.sh writes 0 to reward.txt before anything runs and overwrites it with 1 only when pytest exits cleanly, and a CTRF report is written on every path including collection failure, so a crash still leaves a reward. The sealed answer and the live gateway are generated from one source so they cannot drift, and the gateway's real nginx listens only on loopback inside its sidecar behind the metering front end, so the only way to obtain the configuration is to infer it from behaviour; the reference solution does exactly that, reaching the gateway over the same metered port the agent uses."
category = "Software"
subcategory = "Systems"
tags = ["nginx", "rate-limiting", "reverse-proxy", "black-box", "systems"]
expert_time_estimate_hours = 6
relevant_experience = "I run nginx in front of service tiers and have had to reconstruct undocumented limit_req configurations during proxy migrations, where the running box is the only source of truth. The details that decide such an audit are the ones that do not show up on the common path: that two locations can reference one limit_req_zone with different burst values and so share a counter while looking different, that a shared counter means probing one route moves another, that a burst read off a stream of requests is inflated by the refill that happens between them, and that a staging instance gives you a limited number of calls before it stops, so the probe plan has to be costed against a local nginx before the first request goes to the box under audit."

[verifier]
timeout_sec = 120.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 1800.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
```

## instruction.md
```markdown
we are moving the session tier behind a new gateway and the only copy of its config is the box that is already running. nobody checked it in. it is an nginx 1.27 reverse proxy doing per route rate limiting with limit_req and i need the limits written down, exactly, before we can stand the same thing up anywhere else.

the gateway answers at http://gateway from inside this container. treat it as an evaluation instance. it takes a fixed number of requests over its whole life and then stops, 429 with BUDGET_EXHAUSTED in the body, and there is no reset and no second copy. you get 600 requests total, across every route, for the whole job. every request you send to it counts whether it comes back 200 or refused, so spend them on purpose.

the routes to account for are listed in /app/routes.txt, one path per line. each one is served. a request to a route comes back 200, or it comes back refused with 503 once the limit bites, and that is the whole of what the gateway will tell you. nginx is also installed on this box, so you can bring up your own limit_req configs on the side and check a reading against something you set yourself. that costs nothing. only the gateway is metered.

write the answer to /app/limits.json. one json object with two keys. "zones" is a list, one entry per rate limit counter. each zone has "rate", the counter's rate in requests per second as an integer, and "members", the list of routes that counter governs. each member is an object `{"route": "/x", "burst": <integer>}`, the burst that route allows. "unlimited" is a list of the routes that no counter governs. every route in /app/routes.txt must appear exactly once in the file, either inside one zone's members or in "unlimited", never both and never twice.

so per route i want the rate of the counter sitting behind it and the burst it is allowed. and i want the routes grouped by counter, because a single counter can govern more than one route, and when it does the routes share one running tally even if each sets its own burst. that grouping is half of what i am asking for. it is the thing a config review is supposed to catch, because two routes on one counter starve each other under load and two routes on their own do not.

grading is the whole file against the config i pull off the box, compared as a set. order and whitespace do not matter. it is all or nothing. a counter you split in two, two routes you put together that are not, a burst that is off by one, or a rate pinned on the wrong route, any single one of those and the file is wrong. reporting a limit that is not there fails the same as missing one that is, so do not pad it to be safe and do not trim it to look clean.

this is not one you read off in a couple of calls. the limits do not advertise themselves, two routes can behave the same and not share a counter, and you have one metered instance to learn it all on. i worked the config out by hand against the real box before writing this, so i know it is in there.

nothing else you leave behind is kept. only /app/limits.json comes back.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
