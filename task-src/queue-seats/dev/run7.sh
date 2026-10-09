#!/bin/bash
cd /w
gcc -O2 -o /tmp/qsim solution/qsim.c -lm 2>/dev/null
export PYTHONDONTWRITEBYTECODE=1
python3 solution/plan.py dev/v4/hist/queue_log dev/v4/hist/forecast_2027-03-01.csv /tmp/qsim dev/v4/ref_final.csv >> dev/run7.log 2>&1
python3 dev/spread.py dev/v4/hist/queue_log dev/v4/hist/forecast_2027-03-01.csv /tmp/qsim dev/spread7 boot:1 boot:2 boot:3 boot:4 boot:5 boot:6 boot:7 boot:8 boot:9 boot:10 boot:11 boot:12 seed:1 seed:2 seed:3 seed:4 boot:101 boot:102 boot:103 boot:104 boot:105 boot:106 seed:101 seed:102 >> dev/run7.log 2>&1
python3 dev/abl_plan.py dev/v4/hist/queue_log dev/v4/hist/forecast_2027-03-01.csv /tmp/qsim dev/abl7 naive_talk naive_forecast forecast_no_ringback erlang_c naive_patience wrap_only additive_acw old_faults_wrap flat_talk no_xfer_legs no_xfer no_ghost >> dev/run7.log 2>&1
touch dev/run7.finished
sleep infinity
