#!/usr/bin/env python3
"""raid-salvage authoring generator. runs inside rs-gen (debian bookworm:
e2fsprogs 1.47.0, mdadm 4.2, GNU ddrescue 1.27).

usage: gen.py OUTDIR [SEED]

history
  2023-03 .. 2026-08  share built up by debugfs batches (writes, deletes, links)
  2026-09-02 03:12    bay4 (role 2) kicked from the array        -> A0 = array at drop
  2026-09-02 .. 09-28 array runs degraded, share keeps changing  -> A2 = true array
  2026-09-29 21:40    bay4 re-added, bitmap based recovery starts
  2026-09-30 01:17    bay2 (role 3) read error at recovery front -> array dead
member contents
  roles 0,1,3: A2 striped. role 2: A2 below recovery offset, A0 at and above.
  bay2 and bay1 carry unread areas (zeros + non '+' mapfile entries).
"""
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content as C  # noqa
import mdfmt as M  # noqa

OUT = sys.argv[1]
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20260930
r = random.Random(SEED)

N = 4
CHUNK_S = 128                    # 64 KiB raid chunk
DATA_OFF = 2048                  # sectors
DATA_SECT = 32768                # 16 MiB per member
BM_CHUNK = 64 * 1024
BM_SECT = BM_CHUNK // 512
NBITS = DATA_SECT // BM_SECT
ARRAY_BYTES = (N - 1) * DATA_SECT * 512
BS = 4096
S_ROLE, X_ROLE, Y_ROLE = 2, 3, 1
BAY_OF_ROLE = {1: "bay1", 3: "bay2", 0: "bay3", 2: "bay4"}

WORK = "/tmp/rsgen"
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK + "/src")
CASE_OUT, SEALED = OUT + "/case", OUT + "/sealed"
os.makedirs(CASE_OUT, exist_ok=True)
os.makedirs(SEALED, exist_ok=True)
A_IMG = WORK + "/array.img"


def ts(s):
    import calendar
    import time
    return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M"))


def sh(cmd, env=None, check=True):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, env=e)
    if check and p.returncode != 0:
        raise SystemExit(f"FAIL {cmd}\n{p.stdout}\n{p.stderr}")
    return p


# ---------------------------------------------------------------- filesystem history
srcn = [0]


def src(data):
    srcn[0] += 1
    p = f"{WORK}/src/{srcn[0]}"
    with open(p, "wb") as f:
        f.write(data)
    return p


def q(p):
    return '"' + p + '"'


def batch(when, ops):
    """ops: ('mkdir', path) | ('write', path, bytes) | ('rm', path) | ('ln', target, newpath)"""
    cmds = []
    links = []
    for op in ops:
        if op[0] == "mkdir":
            cmds.append(f"mkdir {q(op[1])}")
        elif op[0] == "write":
            d, b = op[1].rsplit("/", 1)
            cmds.append(f"cd {q(d or '/')}")
            cmds.append(f"write {src(op[2])} {q(b)}")
            cmds.append("cd /")
        elif op[0] == "rm":
            cmds.append(f"rm {q(op[1])}")
        elif op[0] == "ln":
            cmds.append(f"ln {q(op[1])} {q(op[2])}")
            links.append(op[1])
    for t in links:
        cmds.append(f"sif {q(t)} links_count 2")
    with open(WORK + "/cmds", "w") as f:
        f.write("\n".join(cmds) + "\n")
    p = sh(["debugfs", "-w", "-f", WORK + "/cmds", A_IMG],
           env={"E2FSPROGS_FAKE_TIME": str(ts(when))})
    bad = [ln for ln in p.stderr.splitlines()
           if ln.strip() and not ln.startswith("debugfs 1.47")]
    if bad:
        raise SystemExit("debugfs errors:\n" + "\n".join(bad[:20]))


live = {}      # path -> bytes, mirror of the share


def W(path, data):
    live[path] = data
    return ("write", path, data)


def RM(path):
    del live[path]
    return ("rm", path)


projects = ["P-2231 chapel yard", "P-2264 mill annex", "P-2291 harbour lofts", "P-2303 quay studios"]
people = ["mara", "devin", "okafor", "priya"]

sh(f"truncate -s {ARRAY_BYTES} {A_IMG}")
sh(["mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096", "-L", "share",
    "-U", "6f1c2a9e-3b7d-4e55-9a10-2c4d8e71b0a3",
    "-E", "stride=16,stripe_width=48,hash_seed=0b6e6c55-1d2f-4a3b-8c9d-7e6f5a4b3c2d",
    A_IMG], env={"E2FSPROGS_FAKE_TIME": str(ts("2023-03-14 10:22"))})

# 2023: skeleton
ops = [("mkdir", d) for d in ["/admin", "/finance", "/projects", "/it", "/it/logs",
                              "/it/configs", "/photos", "/home", "/archive"]]
ops += [("mkdir", f"/projects/{p}") for p in projects]
ops += [("mkdir", f"/projects/{p}/{s}") for p in projects for s in ["drawings", "minutes", "src"]]
ops += [("mkdir", f"/home/{u}") for u in people]
ops += [("mkdir", "/photos/site visits"), ("mkdir", "/finance/2024"), ("mkdir", "/finance/2025"),
        ("mkdir", "/finance/2026")]
for i in range(6):
    ops.append(W(f"/admin/policy-{i+1:02d}.md", C.text_doc(r, r.randint(3000, 30000), f"policy {i+1}")))
for u in people:
    ops.append(W(f"/home/{u}/notes.md", C.text_doc(r, r.randint(2000, 40000), f"{u} notes")))
batch("2023-04-02 09:10", ops)

# 2024: ledgers, drawings, configs, photos
ops = []
for qn in range(1, 5):
    ops.append(W(f"/finance/2024/ledger-2024-Q{qn}.csv", C.ledger(r, r.randint(2500, 6000), 2024, qn)))
for p in projects:
    for k in range(r.randint(2, 4)):
        ops.append(W(f"/projects/{p}/minutes/meeting {k+1:02d}.md",
                     C.text_doc(r, r.randint(4000, 25000), f"{p} meeting {k+1}")))
    for k in range(r.randint(1, 3)):
        ops.append(W(f"/projects/{p}/src/takeoff_{k}.py", C.code(r, r.randint(10, 60))))
for k in range(5):
    ops.append(W(f"/it/configs/host{k}.conf", C.text_doc(r, r.randint(800, 4000), f"host{k}")))
ops.append(("mkdir", "/archive/scans"))
for k in range(16):
    ops.append(W(f"/archive/scans/scan-2024-{k+1:02d}.txt", C.text_doc(r, r.randint(600000, 1500000), f"scan {k+1}")))
for k in range(6):
    ops.append(W(f"/photos/site visits/IMG_{4100+k}.png", C.png(r, r.randint(120, 260), r.randint(90, 180), 40)))
batch("2024-06-18 14:03", ops)

# 2025: more, some deletes, a hard link, an empty file
ops = []
for qn in range(1, 5):
    ops.append(W(f"/finance/2025/ledger-2025-Q{qn}.csv", C.ledger(r, r.randint(3000, 7000), 2025, qn)))
t = ts("2025-01-01 00:00")
for svc in ["smbd", "nfsd", "backup", "rsync"]:
    data, t = C.logfile(r, r.randint(8000, 20000), t, svc)
    ops.append(W(f"/it/logs/{svc}.log", data))
    ops.append(W(f"/archive/{svc}-2024.log.gz", C.gz(C.logfile(r, 9000, t - 9e6, svc)[0], f"{svc}-2024.log")))
for p in projects:
    for k in range(r.randint(2, 4)):
        ops.append(W(f"/projects/{p}/drawings/{r.choice(['GA','DET','SEC','ELE'])}-{r.randint(100,999)} rev{r.choice('ABC')}.txt",
                     C.text_doc(r, r.randint(40000, 200000), f"{p} drawing register")))
ops.append(W("/admin/.keep", b""))
ops.append(RM("/admin/policy-03.md"))
batch("2025-05-21 11:47", ops)
live["/finance/current-ledger.csv"] = live["/finance/2025/ledger-2025-Q4.csv"]
batch("2025-11-03 16:20", [("ln", "/finance/2025/ledger-2025-Q4.csv", "/finance/current-ledger.csv")])

# 2026 up to the drop
ops = []
for qn in range(1, 3):
    ops.append(W(f"/finance/2026/ledger-2026-Q{qn}.csv", C.ledger(r, r.randint(3000, 7000), 2026, qn)))
for k in range(4):
    ops.append(W(f"/photos/site visits/IMG_{4300+k}.png", C.png(r, r.randint(160, 300), r.randint(120, 200), 50)))
for u in people:
    ops.append(W(f"/home/{u}/todo.txt", C.text_doc(r, r.randint(500, 6000), "todo")))
ops.append(RM("/it/configs/host3.conf"))
for k in (2, 5, 8):
    ops.append(RM(f"/archive/scans/scan-2024-{k:02d}.txt"))
for k in range(7):
    ops.append(W(f"/archive/scans/scan-2026-{k+1:02d}.txt", C.text_doc(r, r.randint(400000, 1200000), f"scan 26 {k+1}")))
for p in projects[2:]:
    ops.append(W(f"/projects/{p}/src/schedule.py", C.code(r, r.randint(30, 90))))
batch("2026-06-30 08:55", ops)
ops = []
for svc in ["smbd", "backup"]:
    old = live[f"/it/logs/{svc}.log"]
    more, t = C.logfile(r, r.randint(3000, 8000), t, svc)
    ops.append(RM(f"/it/logs/{svc}.log"))
    ops.append(W(f"/it/logs/{svc}.log", old + more))
ops.append(W("/finance/2026/ledger-2026-Q3.csv", C.ledger(r, 2500, 2026, 3)))
batch("2026-08-27 17:31", ops)

shutil.copy(A_IMG, WORK + "/A0.img")
live0 = dict(live)

# degraded period: the share keeps changing
T2_BATCHES = []
ops = []
for svc in ["smbd", "nfsd", "rsync"]:
    old = live[f"/it/logs/{svc}.log"]
    more, t = C.logfile(r, r.randint(1500, 5000), t, svc)
    ops.append(RM(f"/it/logs/{svc}.log"))
    ops.append(W(f"/it/logs/{svc}.log", old + more))
ops.append(W("/photos/site visits/IMG_4410.png", C.png(r, 280, 210, 60)))
ops.append(W("/photos/site visits/IMG_4411.png", C.png(r, 240, 180, 60)))
batch("2026-09-04 10:12", ops)
ops = []
q3 = live["/finance/2026/ledger-2026-Q3.csv"]
ops.append(RM("/finance/2026/ledger-2026-Q3.csv"))
ops.append(W("/finance/2026/ledger-2026-Q3.csv", q3 + C.ledger(r, 3500, 2026, 3).split(b"\n", 1)[1]))
for p in projects[1:3]:
    k = len([x for x in live if x.startswith(f"/projects/{p}/minutes/")])
    ops.append(W(f"/projects/{p}/minutes/meeting {k+1:02d}.md", C.text_doc(r, r.randint(6000, 30000), f"{p} meeting {k+1}")))
ops.append(RM("/archive/nfsd-2024.log.gz"))
for k in (1, 6, 11, 14):
    ops.append(RM(f"/archive/scans/scan-2024-{k:02d}.txt"))
for k in range(5):
    ops.append(W(f"/archive/scans/scan-2026-{k+8:02d}.txt", C.text_doc(r, r.randint(300000, 900000), f"scan 26 {k+6}")))
ops.append(("mkdir", "/projects/P-2318 terrace mill"))
for s in ["drawings", "minutes"]:
    ops.append(("mkdir", f"/projects/P-2318 terrace mill/{s}"))
for k in range(4):
    ops.append(W(f"/projects/P-2318 terrace mill/drawings/GA-{110+k} revA.txt",
                 C.text_doc(r, r.randint(30000, 150000), "terrace mill GA")))
batch("2026-09-11 15:40", ops)
ops = []
for u in people[:3]:
    old = live[f"/home/{u}/notes.md"]
    ops.append(RM(f"/home/{u}/notes.md"))
    ops.append(W(f"/home/{u}/notes.md", old + C.text_doc(r, r.randint(3000, 12000), "september")))
ops.append(RM("/photos/site visits/IMG_4102.png"))
ops.append(W("/photos/site visits/IMG_4412.png", C.png(r, 300, 220, 60)))
ops.append(W("/it/configs/host5.conf", C.text_doc(r, 2500, "host5")))
batch("2026-09-18 09:02", ops)
ops = []
for p in projects:
    for name in [x for x in list(live) if x.startswith(f"/projects/{p}/drawings/")][:1]:
        ops.append(RM(name))
        ops.append(W(name.replace("rev", "revised rev"), C.text_doc(r, r.randint(40000, 140000), "revised")))
for svc in ["smbd", "backup"]:
    old = live[f"/it/logs/{svc}.log"]
    more, t = C.logfile(r, r.randint(1000, 3000), t, svc)
    ops.append(RM(f"/it/logs/{svc}.log"))
    ops.append(W(f"/it/logs/{svc}.log", old + more))
ops.append(W("/finance/2026/payment-run-0926.csv", C.ledger(r, 1800, 2026, 3)))
batch("2026-09-26 18:25", ops)

shutil.copy(A_IMG, WORK + "/A2.img")
for img in ("A0.img", "A2.img"):
    p = sh(["e2fsck", "-fn", f"{WORK}/{img}"], check=False)
    if p.returncode != 0:
        raise SystemExit(f"e2fsck {img}: {p.stdout}{p.stderr}")


# ---------------------------------------------------------------- fs introspection
def ls_tree(img):
    """-> {path: (ino, mode, size)} for every entry, recursive."""
    out = {}
    todo = ["/"]
    while todo:
        d = todo.pop()
        p = sh(["debugfs", "-R", f'ls -p "{d}"', img])
        for ln in p.stdout.splitlines():
            m = re.match(r"^/(\d+)/(\d+)/\d+/\d+/([^/]*)/(\d*)/$", ln)
            if not m:
                continue
            ino, mode, name, size = int(m[1]), int(m[2], 8), m[3], m[4]
            if name in (".", "..", "") or ino == 0:
                continue
            path = (d.rstrip("/") + "/" + name)
            out[path] = (ino, mode, int(size or 0))
            if mode & 0o170000 == 0o040000:
                todo.append(path)
    return out


EXT_RE = re.compile(r"^\s*(\d+)/\s*(\d+)\s+\d+/\s*\d+\s+(\d+)\s*-\s*(\d+)\s+(\d+)(?:\s*-\s*(\d+))?\s+(\d+)")


def extents(img, ino):
    """-> (leaf extents [(lstart, pstart, len)], index blocks [p])"""
    p = sh(["debugfs", "-R", f"ex <{ino}>", img])
    leaves, idx = [], []
    for ln in p.stdout.splitlines():
        m = EXT_RE.match(ln)
        if not m:
            continue
        lvl, maxl = int(m[1]), int(m[2])
        if lvl < maxl:
            idx.append(int(m[5]))
        else:
            leaves.append((int(m[3]), int(m[5]), int(m[7])))
    return leaves, idx


tree2 = ls_tree(WORK + "/A2.img")
regs = {}            # ino -> {"paths": [...], "size": n, "ext": [...]}
for path, (ino, mode, size) in tree2.items():
    if mode & 0o170000 == 0o100000:
        regs.setdefault(ino, {"paths": [], "size": size})["paths"].append(path)
    elif mode & 0o170000 != 0o040000:
        raise SystemExit(f"unexpected file type {path}")
blk_owner = {}       # fs block -> (ino, logical block)
for ino, info in regs.items():
    leaves, idx = extents(WORK + "/A2.img", ino)
    info["ext"] = leaves
    for ls_, ps, ln in leaves:
        for k in range(ln):
            blk_owner[ps + k] = (ino, ls_ + k)

with open(WORK + "/A2.img", "rb") as f:
    A2 = f.read()
with open(WORK + "/A0.img", "rb") as f:
    A0 = f.read()

# rdump check: debugfs content == live mirror
sh(["debugfs", "-R", f"rdump / {WORK}/rd", WORK + "/A2.img"]) if os.makedirs(WORK + "/rd") is None else None
for path, data in live.items():
    with open(WORK + "/rd" + path, "rb") as f:
        assert f.read() == data, path
reg_paths = sorted(p for i in regs.values() for p in i["paths"])
assert sorted(live) == reg_paths, (set(live) ^ set(reg_paths))


# ---------------------------------------------------------------- md layer
CH = CHUNK_S * 512


def stripe_members(A):
    dev = [bytearray(DATA_SECT * 512) for _ in range(N)]
    for s in range(DATA_SECT // CHUNK_S):
        pd = M.ls_parity(s, N)
        par = 0
        for i in range(N - 1):
            c = s * (N - 1) + i
            role = (pd + 1 + i) % N
            chunk = A[c * CH:(c + 1) * CH]
            dev[role][s * CH:(s + 1) * CH] = chunk
            par ^= int.from_bytes(chunk, "little")
        dev[pd][s * CH:(s + 1) * CH] = par.to_bytes(CH, "little")
    return dev


D0 = stripe_members(A0)
D2 = stripe_members(A2)


def sect(d, k, row):
    return d[k][row * 512:(row + 1) * 512]


changed = [set() for _ in range(N)]
for k in range(N):
    for row in range(DATA_SECT):
        if sect(D0, k, row) != sect(D2, k, row):
            changed[k].add(row)
dirty = sorted({row // BM_SECT for k in range(N) for row in changed[k]})
dirty_set = set(dirty)
print(f"fs used {sum(len(v) for v in live.values())/2**20:.1f} MiB of {ARRAY_BYTES/2**20:.0f}; "
      f"t0 {sum(len(v) for v in live0.values())/2**20:.1f} MiB")
print(f"regular files {len(reg_paths)}, dirty bitmap chunks {len(dirty)}/{NBITS}, "
      f"S changed sectors {len(changed[S_ROLE])}")


def data_loc(k, row):
    """member sector -> array byte offset of that sector, or None for parity."""
    s, within = divmod(row, CHUNK_S)
    pd = M.ls_parity(s, N)
    if k == pd:
        return None
    i = (k - pd - 1) % N
    return ((s * (N - 1) + i) * CHUNK_S + within) * 512


def owner(k, row):
    """-> ('parity',) | ('file', ino, byte offset in file) | ('meta', block)"""
    a = data_loc(k, row)
    if a is None:
        return ("parity",)
    b, off = divmod(a, BS)
    o = blk_owner.get(b)
    if o is None:
        return ("meta", b)
    return ("file", o[0], o[1] * BS + off)


def s_current(row, R):
    return row < R or (row // BM_SECT) not in dirty_set


def classify(role, rows, R):
    """-> (category, lost data sectors [(k,row)]) or None if placement is not allowed."""
    cats, lost = set(), []
    for row in rows:
        if s_current(row, R):
            cats.add("rec_below" if row < R and (row // BM_SECT) in dirty_set else "rec_clean")
        else:
            if row not in changed[S_ROLE]:
                return None            # contested: S stale-maybe but actually unchanged
            cats.add("lost")
            for k in (role, S_ROLE):
                o = owner(k, row)
                if o[0] == "meta":
                    return None
                if o[0] == "file":
                    lost.append((k, row))
    if len(cats) != 1:
        return None
    return cats.pop(), lost


def touches_file(role, rows):
    return any(owner(role, row)[0] == "file" for row in rows) or \
        any(owner(S_ROLE, row)[0] == "file" and row in changed[S_ROLE] for row in rows)


lost_so_far = set()


def lost_files_of(sects):
    out = set()
    for k, row in sects:
        o = owner(k, row)
        if o[0] == "file" and o[2] < regs[o[1]]["size"]:
            out.add(o[1])
    return out


# recovery offset: recovery front sits in a dirty chunk where S really changed and the
# first unreadable sectors of bay2 (role 3) at the front cost file data.
cands = []
for b in dirty:
    lo, hi = b * BM_SECT, (b + 1) * BM_SECT
    if not (DATA_SECT * 0.35 < lo < DATA_SECT * 0.7):
        continue
    for R in range(lo, hi, 8):
        rows = list(range(R, R + 8))
        c = classify(X_ROLE, rows, R)
        if c and c[0] == "lost" and lost_files_of(c[1]):
            cands.append(R)
if not cands:
    raise SystemExit("no recovery offset candidate")
R = r.choice(cands)
below_dirty = [b for b in dirty if (b + 1) * BM_SECT <= R]
print(f"recovery offset {R} sectors; dirty chunks below {len(below_dirty)}, above {len(dirty) - len(below_dirty)}")

bad = {X_ROLE: [], Y_ROLE: []}     # role -> [(start row, length, status)]
used_rows = set()


def try_place(role, rows, want):
    if any(rw in used_rows for rw in rows):
        return None
    c = classify(role, rows, R)
    if not c or c[0] != want:
        return None
    if want == "lost":
        new = lost_files_of(c[1]) - lost_so_far
        if not new:
            return None
        lost_so_far.update(new)
    if want != "lost" and not touches_file(role, rows):
        return None
    if want == "rec_clean" and not any(owner(role, rw)[0] == "file" for rw in rows):
        return None
    return c


def place(role, want, length, status, region=None, tries=20000):
    for _ in range(tries):
        if region:
            lo, hi = region
        else:
            lo, hi = 0, DATA_SECT - length
        start = r.randrange(lo, hi)
        rows = list(range(start, start + length))
        c = try_place(role, rows, want)
        if c:
            bad[role].append((start, length, status))
            used_rows.update(range(start - CHUNK_S, start + length + CHUNK_S))
            return c
    raise SystemExit(f"could not place {want} on role {role}")


# the read error that stopped the rebuild
front = list(range(R, R + 8))
bad[X_ROLE].append((R, 8, "-"))
lost_so_far.update(lost_files_of(classify(X_ROLE, front, R)[1]))
used_rows.update(range(R - CHUNK_S, R + 8 + CHUNK_S))
# more lost areas on bay2, one of them where bay2 holds parity (only S data is lost)
place(X_ROLE, "lost", r.randint(2, 16), "-")
for _ in range(20000):
    start = r.randrange(R, DATA_SECT - 16)
    ln = r.randint(4, 16)
    rows = list(range(start, start + ln))
    if owner(X_ROLE, start)[0] != "parity" or owner(X_ROLE, start + ln - 1)[0] != "parity":
        continue
    c = try_place(X_ROLE, rows, "lost")
    if c:
        bad[X_ROLE].append((start, ln, "-"))
        used_rows.update(range(start - CHUNK_S, start + ln + CHUNK_S))
        break
else:
    raise SystemExit("no parity-lost placement")
# recoverable through the recovering member: below the front in dirty chunks
placed = 0
for b in r.sample(below_dirty, len(below_dirty)):
    try:
        place(X_ROLE, "rec_below", r.randint(2, 24), "-", region=(b * BM_SECT, (b + 1) * BM_SECT - 24), tries=400)
        placed += 1
    except SystemExit:
        continue
    if placed == 2:
        break
if placed < 2:
    raise SystemExit("could not place two rec_below areas")
# recoverable through the recovering member: clean chunks above the front
place(X_ROLE, "rec_clean", r.randint(2, 24), "-", region=(R + BM_SECT, DATA_SECT - 24))
place(X_ROLE, "rec_clean", 64, "/", region=(R + BM_SECT, DATA_SECT - 64))   # non-scraped
place(X_ROLE, "rec_clean", 16, "*", region=(R + BM_SECT, DATA_SECT - 16))   # non-trimmed
# bay1 (role 1): one recoverable, one lost
place(Y_ROLE, "rec_clean", r.randint(2, 8), "-")
place(Y_ROLE, "lost", r.randint(2, 8), "-")

# ---------------------------------------------------------------- truth
lost_sect = []
for role, regs_ in bad.items():
    for start, ln, _st in regs_:
        rows = list(range(start, start + ln))
        c = classify(role, rows, R)
        assert c is not None
        lost_sect += c[1]
lost_ino = set()
for k, row in lost_sect:
    o = owner(k, row)
    assert o[0] == "file"
    ino, off = o[1], o[2]
    if off < regs[ino]["size"]:
        lost_ino.add(ino)
lost_paths = sorted(p for ino in lost_ino for p in regs[ino]["paths"])
truth = {"files": {}, "lost": lost_paths}
for ino, info in regs.items():
    for p in info["paths"]:
        data = live[p]
        truth["files"][p] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
print(f"lost files: {lost_paths}")

# naive variants, for the record (what each wrong reading would claim)
s_stale_rows = {row for row in changed[S_ROLE] if not s_current(row, R)}
stale_ino = set()
for row in s_stale_rows:
    o = owner(S_ROLE, row)
    if o[0] == "file" and o[2] < regs[o[1]]["size"]:
        stale_ino.add(o[1])
print(f"files with stale bytes on the recovering member (force assemble corrupts): "
      f"{len(stale_ino)}")

# ---------------------------------------------------------------- member images
E_NOW, E_X, E_DROP = 18742, 18740, 18690
UUID = bytes.fromhex("8c3f1e27a94b5d06b2e1c47f9035da6e")
DEV_UUID = {k: hashlib.md5(f"dev{k}{SEED}".encode()).digest() for k in range(N)}
CTIME = M.md_time(ts("2023-03-14 10:19"), 412000)
U_FAIL = M.md_time(ts("2026-09-30 01:17"), 233000)
U_X = M.md_time(ts("2026-09-30 01:17"), 4000)
bits = [b for b in dirty]

members = {}
for k in range(N):
    data = bytearray(D2[k])
    if k == S_ROLE:
        data[R * 512:] = D0[k][R * 512:]
    for start, ln, _st in bad.get(k, []):
        data[start * 512:(start + ln) * 512] = bytes(ln * 512)
    img = bytearray(DATA_OFF * 512) + data
    if k == X_ROLE:
        roles, events, utime, feat, rec = [0, 1, 2, 3], E_X, U_X, M.FEAT_BITMAP, 0
    else:
        roles, events, utime = [0, 1, 2, M.ROLE_FAULTY], E_NOW, U_FAIL
        feat, rec = M.FEAT_BITMAP, 0
        if k == S_ROLE:
            feat, rec = M.FEAT_BITMAP | M.FEAT_RECOVERY, R
    sb = M.superblock(set_uuid=UUID, name="tarn:0", ctime=CTIME, level=5,
                      layout=M.LEFT_SYMMETRIC, size=DATA_SECT, chunk_sectors=CHUNK_S,
                      raid_disks=N, bitmap_offset=8, data_offset=DATA_OFF,
                      data_size=DATA_SECT, super_offset=8, recovery_offset=rec,
                      dev_number=k, device_uuid=DEV_UUID[k], utime=utime, events=events,
                      resync_offset=M.MAX_SECTOR, roles=roles, feature_map=feat)
    bm = M.bitmap(set_uuid=UUID, events=events, events_cleared=E_DROP, sync_size=DATA_SECT,
                  chunksize=BM_CHUNK, sectors_reserved=DATA_OFF - 16, bits=bits, nbits=NBITS)
    img[8 * 512:9 * 512] = sb[:512]
    img[16 * 512:16 * 512 + len(bm)] = bm
    members[k] = img

for k, img in members.items():
    name = BAY_OF_ROLE[k]
    with open(f"{CASE_OUT}/{name}.img", "wb") as f:
        f.write(img)


# ---------------------------------------------------------------- ddrescue mapfiles
def mapfile(name, size, areas, finished, dev):
    """areas: [(byte pos, byte size, status)] unread areas, sorted, inside the image."""
    lines = []
    pos = 0
    for p, s, st in sorted(areas):
        if p > pos:
            lines.append((pos, p - pos, "+"))
        lines.append((p, s, st))
        pos = p + s
    if pos < size:
        lines.append((pos, size - pos, "+"))
    if finished:
        cur, cst, cpass = (lines[-1][0], "+", 3)
        head = ["# Mapfile. Created by GNU ddrescue version 1.27",
                f"# Command line: ddrescue -d -r3 {dev} {name}.img {name}.map",
                "# Start time:   2026-10-01 09:14:02",
                "# Current time: 2026-10-01 09:41:55",
                "# Finished"]
    else:
        cur, cst, cpass = (areas[-1][0], "/", 1)
        head = ["# Mapfile. Created by GNU ddrescue version 1.27",
                f"# Command line: ddrescue -d {dev} {name}.img {name}.map",
                "# Start time:   2026-10-01 10:02:37",
                "# Current time: 2026-10-01 13:26:10",
                "# Scraping failed blocks... (forwards)",
                "# Interrupted by user"]
    out = head + ["# current_pos  current_status  current_pass",
                  f"0x{cur:08X}     {cst}               {cpass}",
                  "#      pos        size  status"]
    out += [f"0x{p:08X}  0x{s:08X}  {st}" for p, s, st in lines]
    return "\n".join(out) + "\n"


DEVNODE = {"bay1": "/dev/sdb", "bay2": "/dev/sdc", "bay3": "/dev/sdd", "bay4": "/dev/sde"}
for k in range(N):
    name = BAY_OF_ROLE[k]
    size = len(members[k])
    areas = []
    for start, ln, st in bad.get(k, []):
        p = (DATA_OFF + start) * 512
        areas.append((p, ln * 512, st))
    txt = mapfile(name, size, areas, finished=(k != X_ROLE), dev=DEVNODE[name])
    with open(f"{CASE_OUT}/{name}.map", "w") as f:
        f.write(txt)

meta = {"R": R, "bad": {str(k): v for k, v in bad.items()}, "dirty": dirty,
        "lost_sectors": lost_sect, "stale_files": len(stale_ino), "seed": SEED}
with open(f"{SEALED}/truth.json", "w") as f:
    json.dump(truth, f, indent=1, sort_keys=True)
with open(f"{SEALED}/gen_meta.json", "w") as f:
    json.dump(meta, f, indent=1)
shutil.copy(WORK + "/A2.img", f"{SEALED}/A2.img")
print("done")
