# cheat attempts (never executed by harbor)

`make_cheats.py` builds four lazy submissions from a folder of correct models (run it in the agent
image). Measured with the verifier on 2026-10-08, every set scores 0:

| attempt | result |
|---|---|
| c1 envelope blocks with the right overall sizes | 0, volume wrong on every part |
| c2 correct solid plus a second solid in the file | 0, exactly one solid required |
| c3 mirror images | 0, no proper rotation matches (all three parts are asymmetric) |
| c4 correct part scaled by 25.4 | 0, volume wrong on every part |

an empty /app/models (nop) also scores 0. the misread battery (one wrong reading of the control
at a time, rebuilt with the reference engine) lives in the author dev tooling (not shipped); its results are summarised in task.toml.
