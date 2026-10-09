# as-machined — submission fields

**Task name:** as-machined
**Category:** Hardware
**Labels:** CAD
**Bundle:** tasks/as-machined/as-machined.zip (rebuild: `python3 kepler-tools/bundle.py task-src/as-machined tasks/as-machined/as-machined.zip`)

**Idea check pitch:**
A manufacturing engineer must deliver STEP solids of three parts exactly as an old Fanuc 0i-MF machining centre cut them on the day a rejected lot ran, within 0.02 mm including unmeasured features. The agent gets today's control backup (ALL-PROG.TXT with custom macro B, CNC-PARA.TXT, TOOLOFST.TXT, EXT_WKZ.TXT), the control's operation history (which only reaches back to six days after the lot), PC-DMIS CMM reports of three serials per part from that lot, and the shop's crib sheet, vise data and setup sheets. It must roll the logged changes back (offsets, wear, a decimal point parameter), diagnose the unlogged ones from the CMM residuals against a forward model (a re-touched work offset, an older drill that was in the spindle, a part turned over the wrong way against the setup sheet) and propagate them through exact Fanuc execution and swept tool geometry to features nobody measured.

**Local gates:** harbor check 11/11; harbor oracle = 1, nop = 0 (local copy installing the same pinned wheels from a local dir; this host cannot download cadquery's big wheels); reference solver reconstructs the lot-day state from the evidence (residuals 0.002 mm); independent point classifier 0 mismatches; misread battery 17/17 wrong reconstructions fail; cheats 0.
**Local hardness probes (opus-5-5):** forward-only version near-solved in 7 min; inverse version 1/3 low effort, 3/3 default effort; hardened version (rapid-drag scratch + turnover evidence only in the QC visual note) **1/3 at default effort** (20-48 min each). Both failures modelled the scratch but kept the setup sheet's X turnover.
