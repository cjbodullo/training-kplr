set -e
bash run_all.sh
for s in 1 2; do ./sim $s 32 8000 0 > simA$s.json & done; wait
python3 gt/mkcand.py sim_meta.json cand.json simA1.json simA2.json
python3 gt/refine.py model.aag model.map netlist.v pairs_base.txt cand.json 0 truth0.json
python3 gt/refine.py model.aag model.map netlist.v pairs_base.txt cand.json 1 truth1.json
cmp truth0.json truth1.json && echo CONVENTIONS AGREE
