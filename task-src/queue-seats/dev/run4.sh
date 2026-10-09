#!/bin/bash
cd /w
gcc -O2 -o /tmp/qsim solution/qsim.c -lm 2>/dev/null
python3 dev/spread.py dev/hist2/queue_log dev/hist2/forecast_2027-03-01.csv /tmp/qsim dev/spread4 boot:1 boot:2 boot:3 boot:4 boot:5 boot:6 boot:7 boot:8 boot:9 boot:10 boot:11 boot:12 seed:1 seed:2 seed:3 seed:4 boot:101 boot:102 boot:103 boot:104 boot:105 boot:106 boot:107 boot:108 seed:101 seed:102 >> dev/spread4.log 2>&1
python3 dev/abl_plan.py dev/hist2/queue_log dev/hist2/forecast_2027-03-01.csv /tmp/qsim dev/abl4 naive_talk erlang_c naive_patience wrap_only additive_acw old_faults_wrap flat_talk no_xfer_legs no_xfer no_ghost >> dev/abl4.log 2>&1
touch dev/run4.finished
sleep infinity
