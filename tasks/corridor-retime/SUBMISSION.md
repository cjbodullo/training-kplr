# corridor-retime

- task name: corridor-retime (afterquery/corridor-retime)
- category: Operations · labels: Logistics
- zip: tasks/corridor-retime/corridor-retime.zip (built from task-src/corridor-retime by kepler-tools/bundle.py)
- author: Shaswat Panda
- generator / calibration: task-src/corridor-retime/dev (gen_history.py, build_bundle.py, retime_ab.py, ab/, ab_final.log)

## local gates (2026-10-08)
- anchor: sumo NEST
- harbor oracle 1.000 (source dir, 20m49s cold) and 1.000 from the extracted zip (12/12 tests)
- harbor nop 0.000
- harbor check 11/11 pass (kepler-tools/harbor_check.py, opus-4-8, 2026-10-08)
- cheats through the verifier image, all 0: no file, existing plan renamed am_peak (entry delays 371-904 s), all green states, 1 s all red, 140 s cycle

## calibration (verifier rules: dd <= 180 s, block back <= 120 s/link/day, 0 teleports, all arrived)
- reference: 10/10 sealed, 20/20 random term mornings (worst dd 6 s, bb 36 s)
- single faults on the sealed set: censor fails 3 days, double count 7, half term survey 10, offsets zero 10, J4 own split 1, all faults 10
- decoys (pass the sealed set): crossed J3 feeders (fails 6/20 random), half term week included, stuck loop days
- honest 110 s cycle variant passes

## v1 submitted 2026-10-08 12:25 — failed quality review (2 blocking)
- difficulty explanation quality: claimed "all offsets zero fails 10/10 sealed". wrong: the dev ablation labelled "offsets" actually set J4 offset 37 s. reference greens with all offsets 0 pass all 10 sealed (reference offsets are 0,-8,0,0).
- graded instances discriminate: existing plan copied through passes sealed day 9 (dd 96 s, bb 57 s), undocumented; coordination dimension overstated.

## v2 fix (2026-10-08)
- re-measured every claimed variant through the verifier image, per sealed day (dev/vlogs/): censor fails d4,7,10; double d1,3,4,5,6,7,10; survey all; J4 split d8; J4 offset +20/+37/+60 all; J2 offset +60 two; all faults all; swap/halfterm/stuck/zero offsets/110 s pass all; existing plan fails all but d9.
- difficulty + verification explanations rewritten: zero offsets stated as safe, coordination trap = moving J4 off J3, per-day null behaviour documented, non-discriminating faults listed as decoys. no code or data changes; oracle/nop unaffected.
- LESSON: label ablations by what they actually set, and re-run every quoted variant through the real verifier image before quoting it.
- v2 local harbor check 11/11 pass (2026-10-08 07:08, kepler-tools/harbor_check.py)

## v3 hardening (2026-10-08) — after local probe showed v2 too easy
- probe evidence (v2): opus-5-5 low effort found every data trap (half term, crossed feeders, stuck loop, double count, capped estate) in ~20 min; v2 would fail easiness.
- new core: Orchard Way phase 2 occupied from 2 Nov (last history week), estate trips x1.75. old plan (110 s, estate 30 s) caps the estate right lane at ~454/h vs ~590 demand, flat 07:30-10:00; only conservation over the last week (07:00-12:00 data) recovers it. developer TA (TRICS, +67/h, "DoS 88.6%, no mitigation") is far too low. estate sat flow ~1666/h measured from capped discharge. ~148/h released east into J3/J4.
- verifier: MAX_DEPART_DELAY 180 -> 300 s (reference tail on random mornings reached 209 s). instruction: phase 2 paragraph, /app/docs TA, 07:00-12:00 data; dropped "is installed" phrase and roleplay opener.
- sealed (10 phase-2 mornings) per-day, through the verifier image (dev/vlogs3): reference passes all (worst dd 85 s, bb 44 s); pre-occupation demand 10/10 fail; mean of term days 10/10; TA uplift 10/10; week-4 stop line no conservation 7 (d1,3,4,5,7,8,10); double count 9 (all but d2); default estate sat 1 (d4); J4 offset 37 s 10/10; existing plan null 10/10. decoys passing all: crossed feeders, no released traffic, zero offsets.
- gates from extracted zip: harbor oracle 1.0, nop 0.0, harbor check 11/11.
- hardness probe (opus-5-5 low, 3 attempts, 2 concurrent) queued as systemd unit corridor-probe-d (waits for a fresh oauth token).
- v3 probe (2026-10-09 00:55, opus-5-5 low, 2 concurrent): host rebooted ~01:55, both killed before writing a plan. Transcripts: both found the phase 2 shift + capped estate and rebuilt it from November daily totals within ~20 min, converged to estate green 46-48 s (reference 47) at C=120 and were tuning offsets by SUMO search. Verdict: v3 very likely TOO EASY too. Not resubmitted.
- final zip rebuilt 2026-10-09 03:50 from v3 source (identical to the gated build): 28 files, 1.0 MB, sha256 52b811cae6f3afc4..., static checks clean.
