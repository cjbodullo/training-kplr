# config-fanout-tree — completed bundle manifest

## task.toml
```toml
artifacts = ["/app/overlay.json"]

[task]
name = "afterquery/config-fanout-tree"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "This is the overlay planning a fleet or platform engineer does when standing up a pull based config sync: decide, for every host, which upstream peer it pulls from, so the whole fleet forms one tree rooted at the seed and the total pull latency is as low as it can be. The optimisation once the graph is known is a textbook minimum spanning arborescence a library solves in one call. The hard part is that the graph the solver needs exists nowhere in one place, and every obvious way to assemble it is wrong. The roster lists hosts that were decommissioned and never answer, so the true set of live hosts is only the hosts that actually respond to a probe. The candidate link list carries a declared latency that is stale bookkeeping, and using it instead of the measured round trip picks the wrong parent for hosts whose two possible upstreams have had their apparent costs swapped. A link the fabric has administratively taken down still shows old successful probes, so trusting the probe alone keeps a cheap link that cannot actually carry a pull. Links are not symmetric: a host can reach a peer while the peer times out in return, and since a pull is initiated by the downstream host, only the direction the puller starts counts, so treating a probe as bidirectional invents links that do not work. The measured latency itself has warmup spikes, so a first sample or a mean or a max reads high and shifts the tree, and only the median over the successful samples is the real cost. Each of these is load bearing and they interact, so a single decommissioned host left in, one administratively down link trusted, one swapped cost, one link used the wrong way, or one latency read off a spike yields an overlay that looks clean on the believed graph and either leans on a link that cannot carry the pull or costs more than the true minimum. There is no local check that tells the planner the real graph. The fleet is fourteen live hosts plus a couple of decommissioned ones, with a spread of candidate links, and the roster, link list, mesh probe log and fabric link state are synthetic, generated deterministically to mirror what such a fleet produces."
solution_explanation = "Reconstruct the true directed peer graph from the feeds, then run a minimum spanning arborescence rooted at h001. Live hosts are exactly the hosts that appear as an endpoint of at least one successful probe, which drops the decommissioned hosts the roster still lists. A directed edge upstream to host exists only when the pulling host's own probes to that upstream succeed and the undirected link is not admin down in the fabric state, so one way links and administratively down links are excluded even where a stale probe or the candidate list suggests them. The cost of an edge is the median of the successful round trip samples for the puller direction, not the declared latency and not a first sample, mean or max, which the warmup spikes distort. With the true live set, usable directed edges and median costs in hand, drop every edge into the seed and take the minimum spanning arborescence with networkx; the reference reproduces the sealed optimum of 132.0. The reference derives the whole graph from the agent visible feeds alone."
verification_explanation = "The deliverable is data and the verifier runs nothing the agent wrote. It loads /app/overlay.json, requires the object shape with root h001 and a parents map whose keys are exactly the live hosts except the seed and whose values are live hosts, with no self pull. It then checks every chosen upstream to host pair is a genuinely usable directed edge of the sealed true graph, that the overlay is acyclic and that the seed reaches every live host, so the plan is one spanning tree rooted at the seed. Finally it charges the plan on the true edge costs and requires the total to equal the minimum, which it recomputes from the sealed graph with a fresh networkx minimum spanning arborescence rather than trusting the stored number, landing on the sealed optimum. Grading is all or nothing and two sided: a feasible but non minimal overlay and a cheap overlay that uses a link absent from the true graph both score 0. The sealed true graph and optimum are baked into the verifier image and absent from the agent container, the reward directory is root owned, and a 0 or 1 reward with a CTRF report is written on every path including a crash."
category = "Software"
subcategory = "Systems"
tags = ["network-planning", "graph-optimization", "data-reconciliation", "infrastructure", "arborescence"]
expert_time_estimate_hours = 7
relevant_experience = "I have planned pull based distribution and sync overlays across server fleets and had to rebuild the true reachability graph from systems that disagree: a cmdb roster that lags decommissions, a hand kept peer link list with stale latencies, mesh prober output with timeouts, one way reachability and warmup spikes, and fabric link state that takes links out of service, then modelled the overlay as a minimum cost arborescence rooted at a seed."

[verifier]
timeout_sec = 300.0
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
we run config sync across the fleet as a pull. every host except the seed pulls its
config off one upstream peer, that peer off its own upstream, all the way back to the
seed h001. so the sync overlay is a tree rooted at h001. i need the cheapest overlay
that actually works. cost of the overlay is the sum of the link costs of the upstreams
you pick, and a link costs the round trip time the pulling host sees to its upstream.
give me the real minimum, not just something that stands up.

write the plan to /app/overlay.json. one json object, key root set to "h001", and key
parents mapping each host that pulls to the host it pulls from. one entry per pulling
host, no entry for the seed. so {"root": "h001", "parents": {"h002": "h001", "h007":
"h003", ...}} and nothing else in the file.

the inputs are under /app, straight off our systems. hosts.csv is the roster the cmdb
carries, columns host_id, region, declared_status. links.csv is the netops team's list
of candidate peer links, columns peer_a, peer_b, declared_rtt_ms. probes.jsonl is the
mesh prober, one json object per line, fields src, dst, rtt_ms, ok. src ran a probe at
dst. ok false is a timeout and rtt_ms is null there. linkstate.txt is the fabric admin
state, lines of the form "admin-down peer_a peer_b" for a link the fabric has taken out
of service, undirected.

a host can only pull from a peer it can actually open a connection to, so the direction
that matters on a link is the one the puller starts, and a link the fabric has down is
not usable at all whatever else you see. the seed pulls from nobody. the roster and the
netops list are both hand maintained and neither is current. plenty of what they say is
in the fleet or wired up does not match what is actually live and reachable, so do not
plan off any one file. work out what the fabric can really do before you build the tree.

grading is all or nothing. the plan is scored against what the fabric can really do. it
has to cover exactly the hosts that are live, every pull has to run over a link that
really works in that direction, the overlay has to be one tree that reaches every live
host from the seed, and the total cost has to equal the true minimum. an overlay that
works but costs more than the minimum fails, and one that looks cheap because it leans on
a link that is not really usable fails too.

grading runs in its own sealed container on a private copy of the answer. it reads only
/app/overlay.json and recomputes the minimum itself, so writing anything under /app or
/logs, or editing the inputs, changes nothing about the score.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
