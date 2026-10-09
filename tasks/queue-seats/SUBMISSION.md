# queue-seats — submission sheet

- Task name: queue-seats  (`[task].name = "afterquery/queue-seats"`)
- Category: Operations · Labels: Logistics
- Zip: tasks/queue-seats/queue-seats.zip (source task-src/queue-seats, built with kepler-tools/bundle.py)
- Author: Shaswat Panda <pandashaswat712@gmail.com>
- Agent budget 14400 s, verifier 300 s, 4 cpu / 8192 MB

## idea check pitch
Contact centre seat plan from raw Asterisk 20 app_queue data: six weeks of queue_log (hashed caller tokens) for three queues plus the live queues.conf/extensions.conf and a forecast for w/c 1 March 2027 trended from Jan-Feb queue entries. Deliverable /app/plan.csv: the smallest seats per open half hour per queue (408 rows) meeting 80% answered within 20 s and at most 5% abandoned after 10 s, judged in steady state. Jan-Feb ran short staffed, which breaks two figures standard WFM takes at face value: (1) the forecast carries 14-32% repeat attempts by lost callers, so it overstates first attempt demand by 16-48%, and the plan's own ring backs must be added back as a fixed point; (2) quick impatient callers hung up before being answered, so logged talk times over-represent long calls, by up to 23%. Around them: handle time = ring + talk + max(wrapuptime, ACW pause), faults wrap 20 -> 60, unforecast transfer load, Kaplan Meier patience, a whole day Monday factor. Graded against bands of the true minimum -2..+1 seat, calibrated on 16 bootstrapped/reseeded reference reruns and validated on 8 held-out reruns. All or nothing.

## local gates (2026-10-07)
- anchor scan: no errors (asterisk named, installed, driven by solve.sh)
- harbor oracle: 1.0 · harbor nop: 0.0
- reference plan 0 of 408 rows outside band; plus_one / minus_one cheats 294 / 285 rows out, reward 0 in the verifier image; missing plan reward 0
- single-misreading ablations on the true model: additive ACW 12, old faults wrap 53, pooled moving patience 3, wrap only 112, flat talk 153, no transfer legs 116, Erlang C 280, naive patience 159, no short abandon exclusion 172, no transfer load 136 rows out (ring ignored: 0, kept for realism)
- harbor check: did not run (AgentSetupTimeoutError after 360 s, same local infra failure as sieve-cutover); not a task finding
- difficulty band: UNMEASURED (no local agent probe)

## v2 (2026-10-08) after quality review failure
- v1 failed quality review: deterministic reproducible / essential difficulty / verification explanation quality (bands narrower than the reference's own seed + data noise).
- fix: bands = nstar +/- 1; 44 reference reruns (seeds + day bootstraps) + shipped ref all 0 rows out; generator/truth/band scripts sealed in tests/groundtruth.
- gates: oracle 1.0, nop 0.0, plus_one/minus_one cheats reward 0 (14 / 12 rows out).
- ablations on final bands: Erlang C 98, no transfer load 126, flat talk 61, no transfer legs 65, naive patience 59, no short abandon exclusion 59, wrap only 4 rows out.
- instruction changed in one sentence (grading tolerance), so the AI check reruns.

## v3 (2026-10-08) hardened after "still easy"
- new inference: caller type selection bias in talk time (two caller kinds, short staffed history). naive per interval AHT, everything else correct: 35 rows out, reward 0.
- reference: talk from calls put through within 5 s of entering the queue; whole day Monday factor per queue (a yes/no Monday test flipped under resampling).
- bands: nstar +/- 1 (nstar - 2 on Monday) union 28 replicates (24 day bootstraps + 4 seed pairs); 16 held-out replicates + reference 0 rows out.
- verifier image (dev/vlogs): reference reward 1; naive talk 35, Erlang C 68, no transfer load 120, sub 10 s abandons counted 52, flat talk 48, transfer legs dropped 31, averaged abandon times 28, wrap only 12, old faults wrap 12 rows out, all reward 0; additive ACW passes alone (decoy). plus_one 1 row out / minus_one 99, both reward 0.

## v4 (2026-10-09) second inference + hardness check
- hardness probe, claude-opus-5-5 low effort, 3 attempts each (kepler-tools/harbor_probe.py): v3 1/3 solved (17 min, found the talk selection by replaying history); v4 0/3 (all found the repeat attempts, none the talk selection; closest 34 rows out after 49 min).
- v4 adds repeat attempts: lost callers ring back (0.55/0.60/0.70 by queue, x0.7 per attempt), forecast trended from entries; caller ids hashed tokens. instruction states how the forecast was built and that ring backs are part of caller behaviour.
- bands: nstar -2..+1 union 16 replicates; 8 held-out replicates + reference 0 rows out.
- verifier image (dev/vlogs7): reference reward 1; forecast at face value 332 rows out, naive talk 78, no transfer load 94, no ghost exclusion 77, Erlang C 56, flat talk 46, transfer legs dropped 35, averaged abandon times 1 (all reward 0); wrap only / old faults wrap / additive ACW / ignoring own ring backs pass alone (decoys). plus_one 14 rows out, minus_three 393, both reward 0.
- fallback: tasks/queue-seats/queue-seats-v3.zip (probed 1/3).
