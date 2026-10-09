# how expected.json was produced

Everything here is authored for this task. The design is a synthetic CIC decimator written for the
task. The agent gets the pre-ECO rtl (synth/cicd_rtl_as_shipped.v). The netlist is built from
synth/cicd_eco.v, which differs from it in two lines: eco1 ties the zero-operand skip off, and eco2
blocks a TEST preload on the cycle a start fires. That rtl is mapped by yosys 0.23 + abc onto the
sky130 hd typical library that ships in the OpenSTA examples (synth/, `run_synth.sh`). Then
synth/cgate.py puts every enable group (all 349 enable flops, 8 groups) behind one sky130 sdlclkp
scan clock gate (GATE = the group's enable, SCE = new port scan_en) and turns the flops into dfxtp on
the gated clock. base.sdc pins scan_en to 0 with set_case_analysis (mission mode).

1. OpenSTA 2.7.0 enumerates every flop -> flop pin path of the frozen netlist.
2. prove/unclock.py rewrites each gated dfxtp as an enable flop on clk whose enable is its gate's GATE
   net (the gate passes an edge exactly when GATE was high in the cycle before; SCE is 0 in mission
   mode). The sdlclkp has no liberty function (statetable only), so this is done by hand. yosys then imports the liberty cell functions and writes the netlist as AIGER with every flop Q and every
   enable net exposed (prove/mkmodel.py). rst_n is low on cycle 0 and high afterwards; unreset flops
   power up to any value (yosys -zinit inputs).
3. For each DE net g and each flop S in the D cone of a flop enabled by g, the property
   "g high => S unchanged over the last k cycles" is checked with abc `pdr -a` (prove/prove.py).
   Candidates came from a bit-parallel random simulation of the same AIG with directed profiles (test-mode
   unlock, input stalls, silence; prove/gen_sim.py). refine.py lowers any disproved candidate and repeats
   until everything is proved, then confirms k+1 is disproved for every pair. truth.json holds k.
4. The same truth was obtained with windows before cycle 0 counted as unchanged and as changed, and the
   proofs and witnesses also hold with all unreset flops powering up to 0, so it does not depend on those
   readings.
5. mkexpected.py turns truth.json into the edge table: setup capture edge k+1 for flop -> gated
   flop D pin paths, 1 for every other path (clock gate GATE pins, ungated flops, io), hold edge 0 everywhere.
