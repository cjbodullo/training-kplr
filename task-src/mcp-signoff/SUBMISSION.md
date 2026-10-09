# mcp-signoff — submission sheet

- **Task name:** mcp-signoff
- **Category:** Hardware
- **Labels:** RTL
- **Zip:** tasks/mcp-signoff/mcp-signoff.zip

## idea check pitch
A constraints engineer signs off a frozen yosys/abc sky130 hd netlist of a CIC decimator with a gain
scaler and APB register file: write /app/exceptions.sdc holding every multicycle exception the block
can legally take, each at its largest multiplier, under a stated stability rule (the source flop's Q
must hold its value for N cycles on every reachable cycle the destination pin captures; edfxtp DE
decides D capture; DE pins and plain flops capture every cycle; no credit for logic masking).
OpenSTA 2.7.0 loads base.sdc plus the file and every one of 11614 path ends must show exactly the
proved setup capture edge and a launch edge hold check. Design intent misleads: a KEY-unlocked test
mode (decimate by 2, a preload that slips in on the start cycle), an exactly-zero idle skip random
stimulus never hits, value-based legal sources with no enable, per bit AGC splits, D vs DE pins and
clear on read. Truth is proved with abc pdr over an AIGER export of the liberty cell functions.
