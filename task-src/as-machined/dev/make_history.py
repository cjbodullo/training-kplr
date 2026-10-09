#!/usr/bin/env python3
"""writes environment/data/cnc/OPRT-HIS.TXT: the control's operation history export, oldest first.
the ring buffer wrapped, so it starts 2026/09/24 06:02; everything before is gone.
usage: make_history.py <out file>"""
import random
import sys

random.seed(918)

# data changes that matter (newest state = today's backup)
KEY = [
    ("2026/09/25 07:14:52", "WEAR OFFSET (H)   NO.004       0.000 ->    -0.030"),
    ("2026/09/27 13:52:07", "PARAMETER         NO.3401   00000001 -> 00000000"),
    ("2026/09/29 06:40:31", "WEAR OFFSET (H)   NO.003      -0.120 ->    -0.050"),
    ("2026/10/02 10:05:44", "WEAR OFFSET (D)   NO.007       0.060 ->     0.120"),
    ("2026/10/03 06:20:13", "WEAR OFFSET (H)   NO.004      -0.030 ->     0.000"),
    ("2026/10/05 14:31:09", "WORK OFFSET       EXT   Z      0.000 ->    -0.200"),
]
# changes to things these parts never use
DECOY = [
    ("2026/09/24 09:11:40", "GEOM OFFSET (H)   NO.011     105.220 ->   104.980"),
    ("2026/09/26 15:02:18", "WORK OFFSET       G58   X   -540.000 ->  -538.750"),
    ("2026/09/26 15:02:41", "WORK OFFSET       G58   Y   -300.000 ->  -301.200"),
    ("2026/09/30 11:47:55", "PROGRAM EDIT      O1655"),
    ("2026/10/01 08:31:02", "WEAR OFFSET (D)   NO.012       0.000 ->     0.040"),
    ("2026/10/06 07:05:36", "GEOM OFFSET (H)   NO.012     117.430 ->   117.505"),
    ("2026/10/07 13:20:19", "PARAMETER         NO.1422     10000. ->     8000."),
]
PROGS = ["O1140", "O2205", "O1610", "O1620", "O1655", "O1655", "O1702"]
ALARMS = ["EX1021 VISE PRESSURE LOW", "PS0010 IMPROPER G-CODE", "EX1007 COOLANT LEVEL LOW",
          "SV0401 IMPROPER V_READY OFF", "OT0500 + OVERTRAVEL ( SOFT 1 )"]


def day_events(day):
    ev = [(f"{day} 06:{random.randint(0, 9):02d}:{random.randint(0, 59):02d}", "POWER ON")]
    t = 6 * 3600 + 15 * 60
    for _ in range(random.randint(6, 14)):
        t += random.randint(900, 4000)
        hh, mm, ss = t // 3600, t % 3600 // 60, t % 60
        if hh >= 17:
            break
        stamp = f"{day} {hh:02d}:{mm:02d}:{ss:02d}"
        r = random.random()
        if r < 0.55:
            ev.append((stamp, f"CYCLE START       {random.choice(PROGS)}"))
        elif r < 0.65:
            ev.append((stamp, f"ALARM             {random.choice(ALARMS)}"))
        elif r < 0.75:
            ev.append((stamp, "RESET"))
        elif r < 0.85:
            ev.append((stamp, f"MODE              {random.choice(['MEM', 'MDI', 'JOG', 'EDIT', 'REF'])}"))
        else:
            ev.append((stamp, "EMERGENCY STOP" if random.random() < 0.2 else "FEED HOLD"))
    ev.append((f"{day} 17:{random.randint(10, 50):02d}:{random.randint(0, 59):02d}", "POWER OFF"))
    return ev


def main():
    days = ["2026/09/24", "2026/09/25", "2026/09/26", "2026/09/29", "2026/09/30", "2026/10/01",
            "2026/10/02", "2026/10/03", "2026/10/05", "2026/10/06", "2026/10/07", "2026/10/08"]
    ev = []
    for d in days:
        ev += day_events(d)
    ev += KEY + DECOY
    ev = [e for e in ev if not (e[0].startswith("2026/10/08") and e[0][11:] > "06:40")]
    ev.sort()
    ev[0] = ("2026/09/24 06:02:11", "POWER ON")
    lines = ["%", "OPERATION HISTORY        VMC-3   FANUC Series 0i-MF Plus",
             "OUTPUT 2026/10/08 06:41:27   ENTRIES %d   (MEMORY FULL, OLDEST ENTRIES OVERWRITTEN)" % len(ev),
             "", "NO.    DATE       TIME      CONTENTS"]
    for k, (stamp, what) in enumerate(ev, 1):
        lines.append(f"{k:05d}  {stamp}  {what}")
    lines.append("%")
    open(sys.argv[1], "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
