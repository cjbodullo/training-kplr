set -e
bash run_synth.sh
sta -no_init -exit pairs.tcl >/dev/null 2>&1
python3 gt/mkmodel.py netlist.v sky130hd_tt.lib model
yosys -q model.ys >/dev/null 2>&1
python3 gt/gen_sim.py model.aag model.map netlist.v pairs_base.txt sim.c sim_meta.json
gcc -O1 -o sim sim.c
