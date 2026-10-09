# how bands.json was made

Sealed with the verifier for review. The verifier itself only reads `/tests/bands.json`; nothing
here runs at grading time.

- `world.py`: the true caller and agent behaviour (arrival shapes, two caller types per queue:
  quick queries with short calls and little patience, complex ones with long calls and a lot,
  talk time by queue, type and block with the billing Monday uplift, ring, ACW pause habit, patience mixture with sub 10 s hang ups
  and the post announcement jump, transfer share, wrap up before and after 22 Feb, and the ring back habit: a caller lost after
  10 s or more rings back with probability 0.55/0.60/0.70 by queue, times 0.7 per further attempt).
- `gen_history.py`: agent level event simulation of Asterisk app_queue over 11 Jan to 20 Feb 2027
  (seeded) that writes `/app/pbx/queue_log` and the forecast csv. Jan-Feb staffing is short
  most of the time, so quick callers often hang up before an agent reaches them, and lost callers
  ring back. The forecast is the true first attempt demand times the entry/first attempt ratio
  the history produced per queue and block (`entry_counts.json` in a regeneration run).
- `qsim.c`: steady state FCFS multi server simulator with ring time, after call work, patience
  and queue timeout. Both the truth and the reference planner use it.
- `truth.py`: for every half hour and queue of the plan week, runs `qsim` on large samples from
  the TRUE distributions (each caller type its own stream, plus the ring backs the plan itself
  causes, solved as a fixed point) (300,000 calls per seat count, common random numbers across seat counts)
  and records nstar (smallest seats meeting SL >= 80% and abandon <= 5%), plus a one seat
  allowance either side where the true figure is within 2 points / 1 point of a target
  (superseded by the wider band built in build_bands.py).
- `spread.py`: re-runs the reference planner (`solution/plan.py`) with fresh model and simulator
  seeds, and on weekday stratified day block bootstraps of the six weeks of history. This is the
  answer a correct method can produce from data of this size.
- `build_bands.py`: band = union of nstar +/- 1 (nstar - 2 on Monday 1 March, whose Monday talk
  factor rests on six Mondays) and every answer from 28 replicates (24 day bootstraps, 4 seed
  pairs). 16 held out replicates and the reference all land inside it.
- `abl_plan.py`: the reference planner with exactly one misreading switched on (talk times from
  every answered call, Erlang C, naive patience, wrap only, ...). Each output plan was graded by
  the real verifier image; the counts quoted in task.toml come from those runs.

Regenerate (from the bundle root, gcc + python3-numpy):

```
gcc -O2 -o tests/groundtruth/qsim tests/groundtruth/qsim.c -lm
cd tests/groundtruth && python3 gen_history.py hist && python3 truth.py truth.json && cd ../..
python3 tests/groundtruth/spread.py tests/groundtruth/hist/queue_log \
    tests/groundtruth/hist/forecast_2027-03-01.csv tests/groundtruth/qsim spread boot:1 ... seed:1 ...
python3 tests/groundtruth/build_bands.py tests/groundtruth/truth.json tests/bands.json spread/*.csv
```
