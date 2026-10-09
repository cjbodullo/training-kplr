cheat attempts (never run by harbor). each was graded with the real verifier image and scores 0.
- plus_one.csv: the reference plan padded by one seat everywhere. 1 row out of band (it already
  contains the correct model, so this is not a shortcut, only a check that padding is not free).
- minus_one.csv: the reference plan one seat lean everywhere. 99 rows out.
- empty / missing plan.csv: fails the presence and coverage checks.
single misreadings of the log (dev runs of solution/plan.py with one switch, see
tests/groundtruth/abl_plan.py): talk time from all answered calls 35 rows out, Erlang C 68,
no transfer load 120, sub 10 s abandons counted 52, flat talk 48, transfer legs dropped 31,
averaged abandon times 28, wrap only 12, old faults wrap 12. additive ACW passes alone.
