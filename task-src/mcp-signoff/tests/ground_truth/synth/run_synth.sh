set -e
yosys -q -l synth.log synth.ys >/dev/null
python3 mkrename.py syn.json rename.ys
yosys -q -p "read_rtlil syn.il; script rename.ys; write_verilog -noattr -noexpr -nohex -nodec netlist.v"
