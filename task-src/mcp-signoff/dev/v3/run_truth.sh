set -e
python3 gt/mkmodel.py model_net.v sky130hd_tt.lib model
yosys -q model.ys >/dev/null 2>&1
python3 gt/gen_sim.py model.aag model.map model_net.v pairs_base.txt sim.c sim_meta.json
gcc -O1 -o sim sim.c
for s in 1 2 3; do ./sim $s 32 8000 0 1 > simA$s.json & done; wait
python3 gt/mkcand.py sim_meta.json cand.json simA1.json simA2.json simA3.json
python3 gt/refine.py model.aag model.map model_net.v pairs_base.txt cand.json 0 truth0.json
python3 gt/refine.py model.aag model.map model_net.v pairs_base.txt cand.json 1 truth1.json
cmp truth0.json truth1.json && echo CONVENTIONS AGREE
