# screen-state (Software / Systems)

Submitted 2026-07-29 as `oVGiBIPlj9wy3W7B3B0a`. **Passed all nine automated
gates -> Needs Review.** difficultyProbe **2 of 8, in_band**; easinessProbe 1 of
3; cheatProbe hacked=false; trajectoryReview pass. Pipeline cost $136.06.

## Shape

Metered clone of a bespoke terminal display unit, the "Ravel DU-3". The agent
writes `/app/term.py` exposing `render(stream: bytes) -> str`, returning the
unit's maintenance dump (80x24 grid, per-cell attributes RLE encoded, cursor,
margins, modes, pen, tab stops) after a byte stream. Graded byte-exact on 40
sealed captures from two verifier-only seeds, all or nothing.

The container publishes the mechanism in full -- SPEC.md gives the grid, the
byte-level parser, every ESC/CSI sequence, the parameter rules, the scrolling
model -- plus `dump.py`, the real serializer, so nobody loses on formatting.
Twelve sample captures ship with no expected dumps.

## The 18 withheld decisions

Pending wrap survives SGR and EL but not ED. BS in column 0 reverse-wraps only
with autowrap on. HT past the last stop raises pending wrap. FF is a display
clear, not a line feed. The blanking family is the crux: ED/EL blank to current
background, ECH to default, ICH to default, DCH to the whole pen, SU/SD to
default -- five siblings, four answers, and the manual documents the fill rule
for scrolling only. Plus IL homing the column where DL does not, IL/DL as a
no-op outside the margins, origin mode homing on switch, CUU/CUD clamping at
margins only under origin mode, DECRC restoring pending wrap, SGR sparing the
REP character, an unknown SGR parameter truncating the list, and a C0 control
inside a CSI executing in place while the sequence continues.

## Calibration

- Every decision ablated on the graded set: each flip alone breaks **8-32 of
  40**. No lottery parameter.
- Textbook reading of all 18, no probing: **0 of 40**.
- One decision wrong: 8-32 captures fail, so reward is still 0.
- Directed probe plan: 18 streams, **360 bytes** = 3% of budget, mechanically
  checked to separate all 18.
- Axis-blind coverage over 8 attacker seeds: median **6003** bytes, max 9018.
- Axis-AWARE coordinate-descent fit: converges at ~**1550** bytes -- which is
  why the 18 axes are NOT enumerated in SPEC.md.
- Meter set to **12000**, ~2x the median blind knee. Shipped captures total
  16231 bytes, so replaying what you are given does not fit.

## Local gates

oracle=1 (source x2, extracted zip x1), nop=0, static lint 43/43, solution
identical to the reference on 40 graded + 160 generated captures + 6000 short
probes + 4000 random/escape-heavy byte-soup streams. Five cheats score 0:
textbook reading, proxy (tested through the live harness, /seal returns 429),
forge (reward.txt + status.json + always-equal str subclass), peek (disk,
modules, gc graph, call stack), respawn (detached grandchild rewriting answers).

`harbor check` could not run locally (AgentAuthenticationError, not logged in) --
auth issue, not a task defect. No local difficulty pre-screen was possible for
the same reason.
