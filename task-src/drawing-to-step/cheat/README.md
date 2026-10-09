# cheat attempts (never executed by harbor)

`make_cheats.py` builds four lazy submissions (run it inside the agent image with a folder of
correct models). Measured with tests/test.sh on 2026-10-07, every set scores 0:

| attempt | result |
|---|---|
| c1 envelope blocks with the right overall sizes | 0, volume wrong on every part |
| c2 correct solid plus a second solid in the file | 0, exactly one solid required |
| c3 mirror images (projection method misread) | 0, the asymmetric parts cannot be matched by any proper rotation |
| (manual) BKT-3302 modelled as the drawn RH part | 0, opposite hand required |
| c4 drawn (not to scale) geometry taken at face value | 0, volume wrong on every part |

an empty /app/models (nop) also scores 0.
