cheat attempts (never run by harbor). each was graded with the real verifier image and scores 0.
- plus_one.csv: the reference plan padded by one seat everywhere. 14 rows out (padding is not free).
- minus_three.csv: the reference plan three seats lean everywhere. 393 rows out.
- empty / missing plan.csv: fails the presence and coverage checks.
single misreadings of the log (solution/plan.py with one switch, tests/groundtruth/abl_plan.py),
rows out of band in the verifier image: forecast taken as first attempts 332, talk time from all
answered calls 78, no transfer load 94, sub 10 s abandons counted 77, Erlang C 56, flat talk 46,
transfer legs dropped 35, averaged abandon times 1. wrap only, old faults wrap, additive ACW and
ignoring the plan's own ring backs pass alone (decoys).
