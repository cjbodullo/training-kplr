#!/usr/bin/env python3
"""raid-salvage v3 authoring generator. runs inside rs-gen (debian bookworm:
e2fsprogs 1.47.0, mdadm 4.2, GNU ddrescue 1.27).

usage: gen3.py OUTDIR [SEED]

history
  2023-03 .. 2026-08  share built up by debugfs batches (writes, deletes, links,
                      a sparse vm image with a depth 1 extent tree, a preallocated
                      scratch image with unwritten extents)
  2026-09-02 03:12    bay4 (role 2) kicked. the journal holds old, checkpointed
                      transactions at this point                 -> A0
  2026-09-02 .. 09-26 degraded, share keeps changing             -> P
  2026-09-29 21:40    bay4 re-added after a reboot (journal restarts at block 1),
                      bitmap based recovery starts
  2026-09-29 22:07 .. 2026-09-30 00:36   three committed jbd2 transactions T1..T3
                      (metadata only in the log, data in place, a revoke)
  2026-09-30 01:16    T4 written to the log, never committed
  2026-09-30 01:17    bay2 read error at the recovery front, array dead
truth = the share after a clean journal recovery of what is on disk = F3.
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
import fsmodel as FM  # noqa
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
NBLK = ARRAY_BYTES // BS
S_ROLE, X_ROLE, Y_ROLE = 2, 3, 0
BAY_OF_ROLE = {0: "bay1", 3: "bay2", 1: "bay3", 2: "bay4"}

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


def sh(cmd, env=None, check=True, inp=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True,
                       env=e, input=inp)
    if check and p.returncode != 0:
        raise SystemExit(f"FAIL {cmd}\n{p.stdout}\n{p.stderr}")
    return p


def rd(img):
    with open(img, "rb") as f:
        return f.read()


def blk(buf, b):
    return buf[b * BS:(b + 1) * BS]


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


def debugfs_batch(img, when, ops):
    """ops: ('mkdir', p) | ('write', p, bytes) | ('rm', p) | ('ln', t, new) | ('mv', old, new)
           | ('punch', p, a, b) | ('falloc', p, a, b) | ('size', p, n)"""
    cmds, links = [], []
    for op in ops:
        if op[0] == "mkdir":
            cmds.append(f"mkdir {q(op[1])}")
        elif op[0] == "write":
            d, b = op[1].rsplit("/", 1)
            cmds += [f"cd {q(d or '/')}", f"write {src(op[2])} {q(b)}", "cd /"]
        elif op[0] == "rm":
            cmds.append(f"rm {q(op[1])}")
        elif op[0] == "ln":
            cmds.append(f"ln {q(op[1])} {q(op[2])}")
            links.append(op[1])
        elif op[0] == "mv":
            cmds += [f"ln {q(op[1])} {q(op[2])}", f"unlink {q(op[1])}"]
        elif op[0] == "punch":
            cmds.append(f"punch {q(op[1])} {op[2]} {op[3]}")
        elif op[0] == "falloc":
            cmds.append(f"fallocate {q(op[1])} {op[2]} {op[3]}")
        elif op[0] == "size":
            cmds.append(f"sif {q(op[1])} size {op[2]}")
        elif op[0] == "mtime":
            cmds.append(f"sif {q(op[1])} mtime @{op[2]}")
    for t in links:
        cmds.append(f"sif {q(t)} links_count 2")
    p = sh(["debugfs", "-w", "-f", "-", img], inp="\n".join(cmds) + "\n",
           env={"E2FSPROGS_FAKE_TIME": str(ts(when))})
    bad = [ln for ln in p.stderr.splitlines()
           if ln.strip() and not ln.startswith("debugfs 1.47")]
    if bad:
        writes = [op[1] for op in ops if op[0] == "write"]
        dup = sorted({w for w in writes if writes.count(w) > 1})
        raise SystemExit(f"debugfs errors in batch {when}: dup writes {dup}\n" + "\n".join(bad[:20]))


live = {}      # path -> bytes, mirror of the share


def W(path, data):
    live[path] = data
    return ("write", path, data)


def RM(path):
    del live[path]
    return ("rm", path)


def batch(when, ops):
    debugfs_batch(A_IMG, when, ops)


def sparse_vm(path, nbytes, holes):
    """write a vm image then punch block ranges out of it -> depth 1 extent tree."""
    data = bytearray(C.png(r, 400, 300, 90) * (nbytes // 30000 + 2))[:nbytes]
    ops = [W(path, bytes(data))]
    for a, b in holes:
        ops.append(("punch", path, a, b))
        data[a * BS:(b + 1) * BS] = bytes((b - a + 1) * BS)
    live[path] = bytes(data[:nbytes])
    return ops


projects = ["P-2231 chapel yard", "P-2264 mill annex", "P-2291 harbour lofts", "P-2303 quay studios"]
people = ["mara", "devin", "okafor", "priya"]

sh(f"truncate -s {ARRAY_BYTES} {A_IMG}")
sh(["mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096", "-g", "4096", "-N", "384",
    "-O", "^flex_bg,^resize_inode", "-J", "size=4", "-L", "share",
    "-U", "6f1c2a9e-3b7d-4e55-9a10-2c4d8e71b0a3",
    "-E", "stride=16,stripe_width=48,hash_seed=0b6e6c55-1d2f-4a3b-8c9d-7e6f5a4b3c2d",
    A_IMG], env={"E2FSPROGS_FAKE_TIME": str(ts("2023-03-14 10:22"))})

# 2023: skeleton
ops = [("mkdir", d) for d in ["/admin", "/finance", "/projects", "/it", "/it/logs",
                              "/it/configs", "/it/vm", "/photos", "/home", "/archive"]]
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

# 2024: ledgers, drawings, configs, photos, the vm images
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
for k in range(12):
    ops.append(W(f"/archive/scans/scan-2024-{k+1:02d}.txt", C.text_doc(r, r.randint(400000, 1100000), f"scan {k+1}")))
for k in range(6):
    ops.append(W(f"/photos/site visits/IMG_{4100+k}.png", C.png(r, r.randint(120, 260), r.randint(90, 180), 40)))
batch("2024-06-18 14:03", ops)
# sparse vm disk: punched every few blocks -> many extents -> index + leaf block
holes = [(a, a + r.randint(0, 2)) for a in range(24, 560, r.randint(7, 9))]
batch("2024-09-02 08:30", sparse_vm("/it/vm/nas-01.vhd", 2400000, holes))
# preallocated scratch image: written head, unwritten tail inside i_size
head = C.text_doc(r, 61000, "scratch header")
live["/it/vm/scratch.img"] = head + bytes(48 * BS - len(head))
batch("2024-09-02 08:41", [("write", "/it/vm/scratch.img", head), ("falloc", "/it/vm/scratch.img", 15, 47),
                           ("size", "/it/vm/scratch.img", 48 * BS)])

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
        while True:
            dn = f"/projects/{p}/drawings/{r.choice(['GA','DET','SEC','ELE'])}-{r.randint(100,999)} rev{r.choice('ABC')}.txt"
            if dn not in live:
                break
        ops.append(W(dn, C.text_doc(r, r.randint(40000, 200000), f"{p} drawing register")))
ops.append(W("/admin/.keep", b""))
ops.append(RM("/admin/policy-03.md"))
ops.append(("mkdir", "/archive/survey 2025"))
for k in range(9):
    ops.append(W(f"/archive/survey 2025/pointcloud-{k+1:02d}.xyz", C.text_doc(r, r.randint(700000, 1100000), f"survey {k+1}")))
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
for k in range(6):
    ops.append(W(f"/archive/scans/scan-2026-{k+1:02d}.txt", C.text_doc(r, r.randint(300000, 900000), f"scan 26 {k+1}")))
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


# ---------------------------------------------------------------- journal helpers
def jwrite(img, txns, close=True):
    """txns: [(blocks [b], contents {b: bytes}, revokes [b], commit bool)] -> debugfs jo/jw/jc."""
    cmds = ["jo -c"]
    for i, (blocks, contents, revokes, commit) in enumerate(txns):
        if blocks and revokes:
            # debugfs 1.47.0 never commits a jw that has both -b and -r, so the revoke
            # records go out as their own committed transaction just before the blocks
            cmds.append("jw -r " + ",".join(map(str, revokes)))
            revokes = []
        args = []
        if blocks:
            fn = f"{WORK}/jtx{i}"
            with open(fn, "wb") as f:
                for b in blocks:
                    f.write(contents[b])
            args += ["-b", ",".join(map(str, blocks))]
        if revokes:
            args += ["-r", ",".join(map(str, revokes))]
        if not commit:
            args.append("-c")
        if blocks:
            args.append(fn)
        cmds.append("jw " + " ".join(args))
    if close:
        cmds.append("jc")
    p = sh(["debugfs", "-w", "-f", "-", img], inp="\n".join(cmds) + "\n")
    bad = [ln for ln in p.stderr.splitlines()
           if ln.strip() and not ln.startswith("debugfs 1.47") and "csum v3" not in ln]
    if bad:
        raise SystemExit("jw errors:\n" + "\n".join(bad))


def logdump(img):
    """-> list of txns [{"seq", "tags": [(fsblk, jblk)], "revokes": [fsblk], "commit": bool}],
    journal block numbers are journal logical blocks."""
    out = sh(["debugfs", "-n", "-R", "logdump -a", img]).stdout
    txns, cur = {}, None
    for ln in out.splitlines():
        m = re.match(r"Found expected sequence (\d+), type (\d+) \((.*)\) at block (\d+)", ln)
        if m:
            seq = int(m[1])
            cur = txns.setdefault(seq, {"seq": seq, "tags": [], "revokes": [], "commit": False,
                                        "blocks": []})
            cur["blocks"].append(int(m[4]))
            if m[2] == "2":
                cur["commit"] = True
            continue
        m = re.match(r"\s+FS block (\d+) logged at journal block (\d+) \(flags (0x[0-9a-f]+)\)", ln)
        if m:
            assert int(m[3], 16) & 1 == 0, "escaped block"
            cur["tags"].append((int(m[1]), int(m[2])))
            cur["blocks"].append(int(m[2]))
            continue
        m = re.match(r"\s+Revoke FS block (\d+)", ln)
        if m:
            cur["revokes"].append(int(m[1]))
    return [txns[k] for k in sorted(txns)]


# old transactions at the drop: the log was in use for years. write a few real
# transactions of current metadata, then recover them (no-op) so the journal is clean.
m_pre = FM.model(A_IMG)
meta_pre = sorted(FM.metadata_blocks(m_pre, NBLK) & (set(m_pre["dirblk"]) |
                  {b for s, n in m_pre["geo"]["it"] for b in range(s, s + n)} |
                  set(m_pre["geo"]["bb"]) | set(m_pre["geo"]["ib"])))
A_buf = rd(A_IMG)
old = []
for i in range(9):
    bl = sorted(r.sample(meta_pre, r.randint(4, 9)))
    old.append((bl, {b: blk(A_buf, b) for b in bl}, [], True))
jwrite(A_IMG, old)
sh(["debugfs", "-w", "-R", "jr", A_IMG])
assert "needs_recovery" not in sh(["dumpe2fs", "-h", A_IMG]).stdout
assert rd(A_IMG)[BS:] != b"" and sh(["e2fsck", "-fn", A_IMG], check=False).returncode == 0

shutil.copy(A_IMG, WORK + "/A0.img")
live0 = dict(live)

# degraded period: the share keeps changing
ops = []
for svc in ["smbd", "nfsd", "rsync"]:
    old_ = live[f"/it/logs/{svc}.log"]
    more, t = C.logfile(r, r.randint(1500, 5000), t, svc)
    ops.append(RM(f"/it/logs/{svc}.log"))
    ops.append(W(f"/it/logs/{svc}.log", old_ + more))
ops.append(W("/photos/site visits/IMG_4410.png", C.png(r, 280, 210, 60)))
ops.append(W("/photos/site visits/IMG_4411.png", C.png(r, 240, 180, 60)))
T_DROP = ts("2026-09-02 03:12") + 41
up = 1873401.552218
klog = []
kt = T_DROP - 86400 * 3
for i in range(40):        # ordinary noise in the days before
    kt += r.randint(600, 9000)
    if kt >= T_DROP - 3600:
        break
    klog.append((kt, r.choice(["e1000e: eno1 NIC Link is Up 1000 Mbps Full Duplex, Flow Control: Rx/Tx",
                               "nfsd: last server has exited, flushing export cache",
                               "EXT4-fs (md0): mounted filesystem with ordered data mode. Quota mode: none.",
                               "smbd[2211]: segfault at 0 ip 000055d1c0a4b3f1 sp 00007ffd4c9b2a10 error 4 in smbd",
                               "audit: type=1400 audit(0.0:91): apparmor=\"STATUS\" operation=\"profile_replace\""])))
klog += [(T_DROP - 2, "ata5.00: exception Emask 0x0 SAct 0x4000 SErr 0x0 action 0x0"),
         (T_DROP - 2, "ata5.00: failed command: WRITE FPDMA QUEUED"),
         (T_DROP - 1, "ata5: hard resetting link"),
         (T_DROP, "ata5.00: disabled"),
         (T_DROP, "md/raid:md0: Disk failure on sdd, disabling device."),
         (T_DROP, "md/raid:md0: Operation continuing on 3 devices."),
         (T_DROP + 7, "md: md0: data-check interrupted.")]
for i in range(8):
    klog.append((ts("2026-09-03 06:00") + i * 9000, "nfsd: last server has exited, flushing export cache"))


def syslog_line(t_, msg):
    import time as _t
    stamp = _t.strftime("%b %e %H:%M:%S", _t.gmtime(t_ + 7200))     # tarn runs on CEST
    return f"{stamp} tarn kernel: [{up + (t_ - T_DROP):12.6f}] {msg}\n"


ops.append(W("/it/logs/kern.log", "".join(syslog_line(a, b) for a, b in sorted(klog)).encode()))
batch("2026-09-04 10:12", ops)
ops = []
q3 = live["/finance/2026/ledger-2026-Q3.csv"]
ops.append(RM("/finance/2026/ledger-2026-Q3.csv"))
ops.append(W("/finance/2026/ledger-2026-Q3.csv", q3 + C.ledger(r, 3500, 2026, 3).split(b"\n", 1)[1]))
for p in projects[1:3]:
    k = len([x for x in live if x.startswith(f"/projects/{p}/minutes/")])
    ops.append(W(f"/projects/{p}/minutes/meeting {k+1:02d}.md", C.text_doc(r, r.randint(6000, 30000), f"{p} meeting {k+1}")))
ops.append(RM("/archive/nfsd-2024.log.gz"))
for k in (1, 6, 11):
    ops.append(RM(f"/archive/scans/scan-2024-{k:02d}.txt"))
for k in range(4):
    ops.append(W(f"/archive/scans/scan-2026-{k+7:02d}.txt", C.text_doc(r, r.randint(300000, 800000), f"scan 26 {k+7}")))
ops.append(("mkdir", "/projects/P-2318 terrace mill"))
for s in ["drawings", "minutes"]:
    ops.append(("mkdir", f"/projects/P-2318 terrace mill/{s}"))
for k in range(4):
    ops.append(W(f"/projects/P-2318 terrace mill/drawings/GA-{110+k} revA.txt",
                 C.text_doc(r, r.randint(30000, 150000), "terrace mill GA")))
RESTORED = "/projects/P-2231 chapel yard/drawings/GA-201 revA (restored).txt"
ops.append(W(RESTORED, C.text_doc(r, 420000, "restored from backup")))
ops.append(("mtime", RESTORED, ts("2024-05-28 12:40")))
batch("2026-09-11 15:40", ops)
ops = []
for u in people[:3]:
    old_ = live[f"/home/{u}/notes.md"]
    ops.append(RM(f"/home/{u}/notes.md"))
    ops.append(W(f"/home/{u}/notes.md", old_ + C.text_doc(r, r.randint(3000, 12000), "september")))
ops.append(RM("/photos/site visits/IMG_4102.png"))
ops.append(W("/photos/site visits/IMG_4412.png", C.png(r, 300, 220, 60)))
ops.append(W("/it/configs/host5.conf", C.text_doc(r, 2500, "host5")))
# the vm behind nas-01.vhd trimmed some space: more holes, the extent leaf is rewritten
vm = bytearray(live["/it/vm/nas-01.vhd"])
for a_ in range(30, 560, 23):
    ops.append(("punch", "/it/vm/nas-01.vhd", a_, a_))
    vm[a_ * BS:(a_ + 1) * BS] = bytes(BS)
live["/it/vm/nas-01.vhd"] = bytes(vm)
batch("2026-09-18 09:02", ops)
ops = []
for p in projects:
    for name in [x for x in list(live) if x.startswith(f"/projects/{p}/drawings/")][:1]:
        ops.append(RM(name))
        ops.append(W(name.replace("rev", "revised rev"), C.text_doc(r, r.randint(40000, 140000), "revised")))
for svc in ["smbd", "backup"]:
    old_ = live[f"/it/logs/{svc}.log"]
    more, t = C.logfile(r, r.randint(1000, 3000), t, svc)
    ops.append(RM(f"/it/logs/{svc}.log"))
    ops.append(W(f"/it/logs/{svc}.log", old_ + more))
ops.append(W("/finance/2026/payment-run-0926.csv", C.ledger(r, 1800, 2026, 3)))
batch("2026-09-26 18:25", ops)

shutil.copy(A_IMG, WORK + "/P.img")

# ---------------------------------------------------------------- the rebuild window
# each batch is one jbd2 transaction. states F1..F3 committed, F4 never committed.
TX_WHEN = ["2026-09-29 22:07", "2026-09-29 23:41", "2026-09-30 00:36", "2026-09-30 01:16"]
ops = []
old_ = live["/it/logs/smbd.log"]
more, t = C.logfile(r, r.randint(800, 1600), t, "smbd")
ops += [RM("/it/logs/smbd.log"), W("/it/logs/smbd.log", old_ + more)]
ops.append(W("/home/priya/handover.md", C.text_doc(r, 14000, "handover")))
ops += sparse_vm("/it/vm/import-tmp.vhd", 1300000,
                 [(a, a + 1) for a in range(12, 300, 6)])
ops.append(W("/projects/P-2318 terrace mill/minutes/meeting 01.md", C.text_doc(r, 9000, "terrace kickoff")))
for k in range(8):       # the evening's scanning run: a burst of new inodes
    ops.append(W(f"/archive/scans/scan-2026-{k+11:02d}.txt", C.text_doc(r, r.randint(15000, 60000), f"scan 26 {k+11}")))
batch(TX_WHEN[0], ops)
shutil.copy(A_IMG, WORK + "/F1.img")
live1 = dict(live)

ops = [W("/finance/2026/payment-run-0929.csv", C.ledger(r, 2200, 2026, 3))]
ops += [RM("/home/mara/todo.txt"), W("/home/mara/todo.txt", C.text_doc(r, 3000, "todo rebuilt"))]
ops += [RM("/home/devin/todo.txt"), RM("/it/vm/import-tmp.vhd")]   # freed blocks get reused in T3
batch(TX_WHEN[1], ops)
shutil.copy(A_IMG, WORK + "/F2.img")
live2 = dict(live)

ops = []
for svc in ["nfsd", "backup"]:
    old_ = live[f"/it/logs/{svc}.log"]
    more, t = C.logfile(r, r.randint(2000, 5000), t, svc)
    ops += [RM(f"/it/logs/{svc}.log"), W(f"/it/logs/{svc}.log", old_ + more)]
ops.append(W("/it/logs/rebuild-0930.log", C.logfile(r, 9000, t, "mdadm")[0]))
for k in range(6):       # photos copied off a phone after midnight
    ops.append(W(f"/photos/site visits/IMG_{4413+k}.png", C.png(r, r.randint(140, 220), r.randint(100, 160), 60)))
batch(TX_WHEN[2], ops)
shutil.copy(A_IMG, WORK + "/F3.img")
live3 = dict(live)

# T4: an uncommitted move into a new folder and an append. data is written in place.
ops = [("mkdir", "/finance/2026/paid"),
       ("mv", "/finance/2026/payment-run-0926.csv", "/finance/2026/paid/payment-run-0926.csv")]
old_ = live["/it/logs/rsync.log"]
more, t = C.logfile(r, 3000, t, "rsync")
ops += [("rm", "/it/logs/rsync.log"), ("write", "/it/logs/rsync.log", old_ + more)]
debugfs_batch(A_IMG, TX_WHEN[3], ops)
shutil.copy(A_IMG, WORK + "/F4.img")
live = live3

for img in ("A0", "P", "F1", "F2", "F3", "F4"):
    p = sh(["e2fsck", "-fn", f"{WORK}/{img}.img"], check=False)
    if p.returncode != 0:
        raise SystemExit(f"e2fsck {img}: {p.stdout}{p.stderr}")

# ---------------------------------------------------------------- build the journal
S = {k: rd(f"{WORK}/{k}.img") for k in ("P", "F1", "F2", "F3", "F4")}
MOD = {k: FM.model(f"{WORK}/{k}.img") for k in ("P", "F1", "F2", "F3", "F4")}
JOURNAL = MOD["F3"]["journal"]
jset = set(JOURNAL)
order = ["P", "F1", "F2", "F3", "F4"]
logged, revoked = [], []
ever = {}                                  # block -> first txn it was logged in
for i in range(1, 5):
    a, b = S[order[i - 1]], S[order[i]]
    meta = FM.metadata_blocks(MOD[order[i]], NBLK)
    ch = [x for x in range(1, NBLK) if x not in jset and blk(a, x) != blk(b, x) and x in meta]
    rv = sorted(x for x in ever if x not in meta and x not in ch and ever[x] < i)
    for x in rv:
        del ever[x]
    for x in ch:
        ever.setdefault(x, i)
    logged.append(ch)
    revoked.append(rv)
print("txn blocks", [len(x) for x in logged], "revokes", revoked)

data3 = set(MOD["F3"]["data"]) | set(MOD["F3"]["uninit"])
data4_new = (set(MOD["F4"]["data"]) - set(MOD["F3"]["data"]) - set(MOD["F3"]["uninit"]))
all_logged = {x for ch in logged for x in ch}
disk = bytearray(S["F3"])
for x in all_logged:
    if x not in data3:
        disk[x * BS:(x + 1) * BS] = blk(S["P"], x)
for x in data4_new:
    disk[x * BS:(x + 1) * BS] = blk(S["F4"], x)
# the revoke trap: a block logged as metadata that is now file data
bite = [x for i, ch in enumerate(logged[:3]) for x in ch
        if x in MOD["F3"]["data"] and blk(S[order[i + 1]], x) != blk(S["F3"], x)]
bite = [x for x in bite if MOD["F3"]["data"][x][1] * BS < MOD["F3"]["inodes"][MOD["F3"]["data"][x][0]]["size"]]
print("revoked blocks that are file data now:", bite)
if not bite:
    raise SystemExit("revoke trap did not form")
DISK = WORK + "/disk.img"
with open(DISK, "wb") as f:
    f.write(disk)
txns = []
for i in range(4):
    st = S[order[i + 1]]
    txns.append((logged[i], {x: blk(st, x) for x in logged[i]}, revoked[i], i < 3))
jwrite(DISK, txns)
disk = bytearray(rd(DISK))
LOG = logdump(DISK)
live_seqs = [t_["seq"] for t_ in LOG]
print("journal txns", [(t_["seq"], len(t_["tags"]), len(t_["revokes"]), t_["commit"]) for t_ in LOG])
assert [t_["commit"] for t_ in LOG if t_["tags"]] == [True, True, True, False], LOG
assert all(t_["commit"] for t_ in LOG if not t_["tags"]), LOG
seq_batch = {}
for t_ in LOG:
    if t_["tags"]:
        i = [sorted(ch) for ch in logged].index(sorted(f for f, _ in t_["tags"]))
        seq_batch[t_["seq"]] = i
assert "needs_recovery" in sh(["dumpe2fs", "-h", DISK]).stdout

# real recovery must give exactly F3
chk = WORK + "/chk.img"
shutil.copy(DISK, chk)
sh(["e2fsck", "-fy", "-E", "journal_only", chk], check=False)
sh(["debugfs", "-R", f"rdump / {WORK}/rd3", chk]) if os.makedirs(WORK + "/rd3") is None else None
for path, data in live3.items():
    with open(WORK + "/rd3" + path, "rb") as f:
        assert f.read() == data, f"replay mismatch {path}"
reg3 = sorted(p_ for p_, v in MOD["F3"]["tree"].items() if v[1] == "reg")
assert reg3 == sorted(live3), set(reg3) ^ set(live3)
rep = rd(chk)
bad = [x for x in range(1, NBLK) if x not in jset and x not in data4_new
       and blk(rep, x) != blk(S["F3"], x)]
assert not bad, f"replayed image differs from F3 in blocks {bad[:10]}"
print("journal recovery of the disk image reproduces F3")


# final source of every fs block after recovery: (txn index, journal logical block) or None
def final_sources(log):
    revs = {}
    for t_ in log:
        if t_["commit"]:
            for x in t_["revokes"]:
                revs[x] = max(revs.get(x, 0), t_["seq"])
    src_ = {}
    for t_ in log:
        if not t_["commit"]:
            continue
        for fsb, jb in t_["tags"]:
            if revs.get(fsb, 0) >= t_["seq"]:
                continue
            src_[fsb] = (t_["seq"], jb)
    return src_


FSRC = final_sources(LOG)
jstruct = {jb for t_ in LOG for jb in t_["blocks"] if jb not in {j for _, j in t_["tags"]}}
jstruct |= {0}
last_jb = max(jb for t_ in LOG for jb in t_["blocks"])
jstruct |= set(range(last_jb + 1, last_jb + 4))
copy_final = {jb: fsb for fsb, (_s, jb) in FSRC.items()}

# ---------------------------------------------------------------- md layer
CH = CHUNK_S * 512
A0 = rd(WORK + "/A0.img")
DISKB = bytes(disk)


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
D2 = stripe_members(DISKB)
changed = [set() for _ in range(N)]
for k in range(N):
    a, b = D0[k], D2[k]
    for row in range(DATA_SECT):
        if a[row * 512:(row + 1) * 512] != b[row * 512:(row + 1) * 512]:
            changed[k].add(row)
dirty = sorted({row // BM_SECT for k in range(N) for row in changed[k]})
dirty_set = set(dirty)
print(f"regular files {len(reg3)}, dirty bitmap chunks {len(dirty)}/{NBITS}")


def data_loc(k, row):
    s, within = divmod(row, CHUNK_S)
    pd = M.ls_parity(s, N)
    if k == pd:
        return None
    i = (k - pd - 1) % N
    return ((s * (N - 1) + i) * CHUNK_S + within) * 512


def row_of_array(a):
    """array byte -> (member, row)"""
    c, within = divmod(a // 512, CHUNK_S)
    s, i = divmod(c, N - 1)
    pd = M.ls_parity(s, N)
    return (pd + 1 + i) % N, s * CHUNK_S + within


# ---------------------------------------------------------------- what bay4 still proves
# above the front bay4 holds the array exactly as it was when it dropped out. a block
# owned by a file whose inode ctime is before the drop cannot have changed since (any
# write or reallocation moves ctime), so bay4's copy of it is current whatever the
# bitmap says. a parity sector is current if all three data sectors of its row are.
reg3 = {i: v for i, v in MOD["F3"]["inodes"].items() if v["kind"] == "reg"}
stats = FM._dbg_batch(WORK + "/F3.img", [f"stat <{i}>" for i in sorted(reg3)])
CTIME, MTIME = {}, {}
for i, st in zip(sorted(reg3), stats):
    CTIME[i] = int(re.search(r"ctime: 0x([0-9a-f]+)", st)[1], 16)
    MTIME[i] = int(re.search(r"mtime: 0x([0-9a-f]+)", st)[1], 16)
near = [i for i, c in CTIME.items() if abs(c - T_DROP) < 86400]
assert not near, f"ctimes too close to the drop: {near}"
OLD_INO = {i for i, c in CTIME.items() if c < T_DROP}
OLD_BLOCKS = {b for b, (i, _l) in list(MOD["F3"]["data"].items()) + list(MOD["F3"]["uninit"].items())
              if i in OLD_INO}
MTIME_OLD_BLOCKS = {b for b, (i, _l) in MOD["F3"]["data"].items() if MTIME[i] < T_DROP}
RESTORED_INO = MOD["F3"]["tree"][RESTORED][0]
assert RESTORED_INO not in OLD_INO and MTIME[RESTORED_INO] < T_DROP


def rehab(row, blocks=None):
    blocks = OLD_BLOCKS if blocks is None else blocks
    a = data_loc(S_ROLE, row)
    if a is not None:
        return a // BS in blocks
    return all(data_loc(m, row) // BS in blocks for m in range(N) if m != S_ROLE)


REHAB_ROWS = [row for row in range(R if False else 0, DATA_SECT) if rehab(row)]
for row in REHAB_ROWS:
    assert D0[S_ROLE][row * 512:(row + 1) * 512] == D2[S_ROLE][row * 512:(row + 1) * 512], \
        f"bay4 row {row} is provably current but differs"
print(f"rows where bay4 is provably current from file ctimes: {len(REHAB_ROWS)}")


# ---------------------------------------------------------------- what an undetermined sector costs
G3 = MOD["F3"]["geo"]
INO3 = MOD["F3"]["inodes"]
it_blocks = {}
for g, (s0, n) in enumerate(G3["it"]):
    for k in range(n):
        it_blocks[s0 + k] = (g, k)
jpos = {pb: jl for jl, pb in enumerate(JOURNAL)}
F3B = S["F3"]


def inode_bytes(buf, ino):
    b, off = FM.inode_loc(G3, ino)
    return buf[b * BS + off:b * BS + off + G3["isz"]]


def inodes_in(b, sec):
    g, k = it_blocks[b]
    first = g * G3["ipg"] + (k * BS + sec * 512) // G3["isz"] + 1
    return list(range(first, first + 512 // G3["isz"]))


def cost_final(x, sec, via):
    """fs block x, 512 byte sector sec of its FINAL content undetermined.
    via = None (in place) or txn seq of the journal copy. -> (tag, {ino}) or ('FORBID', reason)"""
    if x in (0, 1):
        return "FORBID", "sb/gdt"
    if x in it_blocks:
        hit = set()
        for ino in inodes_in(x, sec):
            info = INO3.get(ino)
            if ino <= 11:
                if info or ino in (2, 8):
                    return "FORBID", f"reserved inode {ino}"
                continue
            if info is None:
                continue
            if info["kind"] == "dir":
                return "FORBID", f"dir inode {ino}"
            if via is not None:
                # the copy must really carry news for this inode, else the old in place
                # inode would be an arguable answer
                i = seq_batch[via]
                prev = S[order[i]]
                if inode_bytes(prev, ino) == inode_bytes(S[order[i + 1]], ino):
                    return "FORBID", f"inode {ino} unchanged in its txn"
            hit.add(ino)
        if via is not None:
            return ("jcopy_it_lost" if hit else "jcopy_it_free"), hit
        return ("it_lost" if hit else "it_free"), hit
    if x in MOD["F3"]["dirblk"]:
        return "FORBID", "dir block"
    if x in MOD["F3"]["extblk"]:
        if via is not None:
            return "FORBID", "journaled extent block"
        return "ext_lost", {MOD["F3"]["extblk"][x]}
    if via is not None:
        return "jcopy_other", set()
    if x in MOD["F3"]["data"]:
        ino, lb = MOD["F3"]["data"][x]
        if lb * BS + sec * 512 < INO3[ino]["size"]:
            return "data_lost", {ino}
        return "data_eof", set()
    if x in MOD["F3"]["uninit"]:
        return "uninit", set()
    return "free", set()


def cost(a):
    """array sector number a (512 B) of the on disk image undetermined."""
    x, sec = divmod(a, BS // 512)
    if x in jpos:
        jl = jpos[x]
        if jl in jstruct:
            return "FORBID", "journal structure"
        if jl in copy_final:
            fsb = copy_final[jl]
            return cost_final(fsb, sec, FSRC[fsb][0])
        return "jold", set()
    if x in FSRC:
        return "it_superseded" if x in it_blocks else "superseded", set()
    return cost_final(x, sec, None)


# ---------------------------------------------------------------- loss placement
bad = {X_ROLE: [], Y_ROLE: []}        # role -> [(start row, length, status)]
used_rows = set()
R = None


def unread_rows():
    u = {k: set() for k in bad}
    for k, regs_ in bad.items():
        for start, ln, _st in regs_:
            u[k].update(range(start, start + ln))
    return u


def s_stale(row):
    return row >= R and (row // BM_SECT) in dirty_set


def undetermined(areas, use_rehab=True):
    """areas {role: [(start, len, st)]} -> (undet array sectors, recoverable rows, problem)"""
    u = {k: set() for k in (X_ROLE, Y_ROLE)}
    for k, regs_ in areas.items():
        for start, ln, _st in regs_:
            u[k].update(range(start, start + ln))
    out, rec, prob = set(), set(), None
    for row in set().union(*u.values()):
        unk = {k for k in u if row in u[k]}
        if s_stale(row) and not (use_rehab and rehab(row)):
            unk.add(S_ROLE)
        if len(unk) >= 2:
            for k in unk:
                a = data_loc(k, row)
                if a is not None:
                    out.add(a // 512)
        else:
            rec.add(row)
    return out, rec, prob


BYTAG = {}


def tags_of(sects):
    tags, lost = {}, set()
    BYTAG.clear()
    for a in sects:
        t_, inos = cost(a)
        if t_ == "FORBID":
            return None, inos
        tags[t_] = tags.get(t_, 0) + 1
        lost |= inos
        BYTAG.setdefault(t_, set()).update(inos)
    return tags, lost


def rec_touch(rows, role):
    """recoverable rows: what the unread member held there (for targeting)."""
    t = set()
    for row in rows:
        a = data_loc(role, row)
        if a is None:
            t.add("parity")
        else:
            t.add(cost(a // 512)[0])
    return t


lost_so_far = set()
PROTECT = {MOD["F3"]["tree"]["/it/vm/scratch.img"][0],   # the unwritten extent trap must stay recoverable
           MOD["F3"]["tree"]["/it/logs/kern.log"][0]}      # the drop time has to be readable
# the file that now lives in a revoked block must stay recoverable, or ignoring the
# revoke would cost nothing
BITE_INO = {MOD["F3"]["data"][x][0] for x in bite}
PROTECT |= BITE_INO
print("revoke victims:", sorted(p_ for i in BITE_INO for p_ in INO3[i]["paths"]))
NOMORE = set()            # every lost file has exactly one cause


def superseded_inodes(sects):
    out = set()
    for a in sects:
        x, sec = divmod(a, BS // 512)
        if x in it_blocks and x not in jpos and x in FSRC:
            out |= {i for i in inodes_in(x, sec) if INO3.get(i, {}).get("kind") == "reg"}
    return out


def try_areas(new, want, allow, need_new_loss=False):
    """new: {role: [(start, len, st)]}. want: tag that must appear among the newly
    undetermined sectors (or, for recoverable placements, among what was read over)."""
    rows = {rw for regs_ in new.values() for s0, ln, _ in regs_ for rw in range(s0, s0 + ln)}
    if rows & used_rows:
        return None
    merged = {k: list(bad[k]) + list(new.get(k, [])) for k in bad}
    old_u, _, _ = undetermined(bad)
    all_u, rec, prob = undetermined(merged)
    if prob:
        return None
    fresh = all_u - old_u
    if want.startswith("rec:"):
        if fresh:
            return None
        hit = set()
        for k, regs_ in new.items():
            for s0, ln, _ in regs_:
                hit |= rec_touch(range(s0, s0 + ln), k)
        wants = set(want[4:].split("|"))
        return hit if hit & wants else None
    tags, lost = tags_of(fresh)
    if tags is None or want not in tags:
        return None
    if any(t_ not in allow and t_ != want for t_ in tags):
        return None
    if need_new_loss and not (lost - lost_so_far):
        return None
    if lost & PROTECT or lost & NOMORE:
        return None
    # a trap file is lost through its trap alone
    if want in ("ext_lost", "it_lost", "jcopy_it_lost"):
        other = set().union(*(v for k_, v in BYTAG.items() if k_ != want))
        if BYTAG[want] & other:
            return None
    if want == "it_superseded":
        sup = superseded_inodes(fresh)
        if not sup or sup & (lost | lost_so_far):
            return None
        return tags, lost, sup
    return tags, lost


def commit_areas(new, res):
    for k, regs_ in new.items():
        for s0, ln, st in regs_:
            bad[k].append((s0, ln, st))
            used_rows.update(range(s0 - 8, s0 + ln + 8))
    if isinstance(res, tuple):
        lost_so_far.update(res[1])
        NOMORE.update(res[1])
        if len(res) == 3:
            PROTECT.update(res[2])
            print("  protected (superseded inodes):", sorted(res[2]))
    print("  placed", new, "->", res if not isinstance(res, tuple) else (res[0], sorted(res[1])))


def place(name, gen, want, allow=(), need_new_loss=False, tries=40000):
    for _ in range(tries):
        new = gen()
        if new is None:
            continue
        res = try_areas(new, want, set(allow), need_new_loss)
        if res:
            print(name)
            commit_areas(new, res)
            return res
    if getattr(gen, "targets", None):
        print(f"DIAG {name}: minimal covers")
        for a in gen.targets[:: max(1, len(gen.targets) // 40)]:
            k, row = row_of_array(a * 512)
            line = [f"sect {a} member {k} row {row} stale {s_stale(row)} used {row in used_rows}"]
            for m in range(N):
                d = data_loc(m, row)
                line.append(f"{m}:{cost(d // 512)[0] if d is not None else 'parity'}")
            print("   ", " ".join(line))
    raise SystemExit(f"could not place {name}")


HARMLESS = ("free", "data_eof", "jold", "superseded", "it_superseded", "it_free",
            "jcopy_it_free", "jcopy_other", "uninit")

# recovery offset: in a dirty chunk below the live log, where bay2's first bad sectors
# (with bay4 stale) cost file data
jrows = sorted(row_of_array(JOURNAL[jl] * BS)[1] for jl in copy_final)
cands = []
for b in dirty:
    lo, hi = b * BM_SECT, (b + 1) * BM_SECT
    if not (DATA_SECT * 0.2 < lo and hi < min(jrows) - BM_SECT):
        continue
    for Rc in range(lo, hi, 8):
        R = Rc
        res = try_areas({X_ROLE: [(Rc, 8, "-")]}, "data_lost", set(HARMLESS), True)
        if res:
            cands.append(Rc)
if not cands:
    raise SystemExit("no recovery offset candidate")
ext_row_min = min(row_of_array(b * BS)[1] for b in MOD["F3"]["extblk"])
low = [c for c in cands if c < ext_row_min - BM_SECT]
R = r.choice(low or cands)
print(f"extent blocks from member row {ext_row_min}; front candidates below them: {len(low)}")
print(f"recovery offset {R} sectors (journal copies at member rows {jrows[0]}..{jrows[-1]})")
place("front", lambda: {X_ROLE: [(R, 8, "-")]}, "data_lost", HARMLESS, True, tries=1)


def x_only(lo, hi, lmin, lmax, st="-", role=None):
    def g():
        ln = r.randint(lmin, lmax)
        if hi - ln <= lo:
            return None
        return {role if role is not None else X_ROLE: [(r.randrange(lo, hi - ln), ln, st)]}
    return g


def xy_overlap(lo, hi):
    """bay2 and bay1 both unread on a few rows, each area sticking out on its own side,
    so either one alone would have been covered by parity."""
    def g():
        if hi - 40 <= lo:
            return None
        a = r.randrange(lo, hi - 40)          # first row both are unread
        ov = r.randint(1, 6)                  # rows both are unread
        xs = a - r.randint(1, 10)
        ye = a + ov + r.randint(1, 10)
        if xs < 0:
            return None
        return {X_ROLE: [(xs, a + ov - xs, "-")], Y_ROLE: [(a, ye - a, "-")]}
    return g


def rows_of_block(x):
    k, row = row_of_array(x * BS)
    return k, row


def around(row, maxlen=10):
    a = row - r.randint(0, maxlen - 1)
    return a, row - a + 1 + r.randint(0, maxlen - 1)


def cover(targets):
    """generator of areas that make one of the target array sectors undetermined."""
    def g():
        a = r.choice(targets)
        k, row = row_of_array(a * 512)
        if s_stale(row) and not rehab(row):
            if k in (X_ROLE, Y_ROLE):
                s0, ln = around(row)
                return {k: [(s0, ln, "-")]}
            if k == S_ROLE:
                s0, ln = around(row)
                return {r.choice([X_ROLE, Y_ROLE]): [(s0, ln, "-")]}
            return None
        if k not in (X_ROLE, Y_ROLE):
            return None
        other = Y_ROLE if k == X_ROLE else X_ROLE
        s0, ln = around(row, 8)
        # the other disk is unread on an overlapping, offset stretch
        o0 = row - r.randint(0, 3)
        oln = row - o0 + 1 + r.randint(2, 12)
        return {k: [(s0, ln, "-")], other: [(o0, oln, "-")]}
    g.targets = targets
    return g


def sectors_of(blocks):
    return [b * 8 + i for b in blocks for i in range(8)]


jcopy_it = sectors_of(JOURNAL[jl] for jl, fsb in copy_final.items() if fsb in it_blocks)
it_sup = sectors_of(b for b in it_blocks if b in FSRC)
it_inplace = sectors_of(b for b in it_blocks if b not in FSRC)
print("targets: journal copies of inode tables", len(jcopy_it) // 8, "blocks; inode table blocks superseded",
      len(it_sup) // 8, "in place only", len(it_inplace) // 8)
place("journal copy of an inode table block", cover(jcopy_it), "jcopy_it_lost",
      HARMLESS + ("data_lost",), True)
place("in place inode table sector superseded by the log", cover(it_sup), "it_superseded",
      ("free", "data_eof", "superseded", "it_free", "uninit", "jold"))
place("in place inode table sector lost", cover(it_inplace), "it_lost", HARMLESS + ("data_lost",), True)
place("extent leaf of the sparse vm image", cover(sectors_of(MOD["F3"]["extblk"])), "ext_lost",
      HARMLESS + ("data_lost",), True)
place("unwritten extent of the preallocated image", cover(sectors_of(MOD["F3"]["uninit"])), "uninit",
      ("free", "data_eof", "jold", "superseded", "it_superseded", "it_free"))
# bay2 holds parity, bay4's stale data sector is what goes
def parity_lost():
    st = r.randrange(R, DATA_SECT - 16)
    ln = r.randint(4, 16)
    if data_loc(X_ROLE, st) is not None or data_loc(X_ROLE, st + ln - 1) is not None:
        return None
    return {X_ROLE: [(st, ln, "-")]}
place("bay2 parity, bay4 stale", parity_lost, "data_lost", HARMLESS, True)
# recoverable through the recovering member below the front, and through parity elsewhere
below_dirty = [b for b in dirty if (b + 1) * BM_SECT <= R]
for i in range(2):
    place(f"below the front {i}", lambda: (lambda b: {X_ROLE: [(r.randrange(b * BM_SECT, (b + 1) * BM_SECT - 24), r.randint(2, 24), "-")]})(r.choice(below_dirty)),
          "rec:data_lost")
if os.environ.get("DIAG"):
    from collections import Counter
    cnt = Counter()
    for row in range(R + BM_SECT, DATA_SECT):
        if (row // BM_SECT) in dirty_set:
            cnt["(dirty)"] += 1
            continue
        a = data_loc(X_ROLE, row)
        cnt["parity" if a is None else cost(a // 512)[0]] += 1
    print("DIAG bay2 above the front:", dict(cnt))
    used = sum(1 for rw in range(R + BM_SECT, DATA_SECT) if rw in used_rows)
    print("DIAG used rows above front", used)
place("clean chunk above the front", x_only(R + BM_SECT, DATA_SECT - 24, 2, 24), "rec:data_lost|it_lost|jcopy_it_lost|ext_lost|it_superseded")
place("non-scraped", x_only(R + BM_SECT, DATA_SECT - 64, 64, 64, "/"), "rec:data_lost|it_lost|jcopy_it_lost|ext_lost|it_superseded")
place("non-trimmed", x_only(R + BM_SECT, DATA_SECT - 16, 16, 16, "*"), "rec:data_lost|it_lost|jcopy_it_lost|ext_lost|it_superseded")
place("bay1 bad spot that parity covers", x_only(0, R - 16, 2, 8, role=Y_ROLE), "rec:data_lost")
place("bay1 lost with bay4 stale", lambda: (lambda st: {Y_ROLE: [(st, r.randint(2, 8), "-")]})(r.randrange(R, DATA_SECT - 8)),
      "data_lost", HARMLESS, True)

# bay2 unread where bay4 is bitmap-stale but provably current: every textbook reading
# writes these files off, the ctime argument gets them back
def rehab_place(name, parity, tries=40000):
    rows = [row for row in range(R, DATA_SECT) if s_stale(row) and rehab(row)
            and (data_loc(S_ROLE, row) is None) == parity and row not in used_rows]
    print(f"{name}: {len(rows)} candidate rows")
    for _ in range(tries):
        if not rows:
            break
        row = r.choice(rows)
        s0, ln = around(row, 8)
        new = {X_ROLE: [(s0, ln, "-")]}
        rws = set(range(s0, s0 + ln))
        if rws & used_rows:
            continue
        merged = {k: list(bad[k]) + list(new.get(k, [])) for k in bad}
        if undetermined(merged)[0] - undetermined(bad)[0]:
            continue
        tb = undetermined(merged, False)[0] - undetermined(bad, False)[0]
        tags_tb, lost_tb = tags_of(tb)
        if tags_tb is None or not (lost_tb - lost_so_far - PROTECT):
            continue
        commit_areas(new, "rehab")
        PROTECT.update(lost_tb)
        print(f"{name}\n  textbook would write off {sorted(lost_tb)}")
        return lost_tb
    raise SystemExit(f"could not place {name}")


RESCUED = set()
RESCUED |= rehab_place("bay4 data sector provably current", parity=False)
RESCUED |= rehab_place("bay4 parity sector provably current", parity=True)
# the restored drawing: old mtime, new ctime, its blocks on bay4 are stale
rest_blocks = {b for b, (i, _l) in MOD["F3"]["data"].items() if i == RESTORED_INO}
rest_sects = [b * 8 + k for b in rest_blocks for k in range(8)]
rest_rows = [row_of_array(a * 512)[1] for a in rest_sects
             if row_of_array(a * 512)[0] == S_ROLE and s_stale(row_of_array(a * 512)[1])]
print(f"restored file sectors on bay4 above the front in dirty chunks: {len(rest_rows)}")
place("restored drawing, mtime lies", lambda: (lambda row: {X_ROLE: [around(row, 6) + ("-",)]})(r.choice(rest_rows)),
      "data_lost", HARMLESS + ("data_lost",), True)
assert RESTORED_INO in lost_so_far, "restored drawing not lost"

# ---------------------------------------------------------------- truth
UND, _, _ = undetermined(bad)
tags, lost_ino = tags_of(UND)
assert tags is not None
print("undetermined sector tags", tags)
lost_paths = sorted(p_ for ino in lost_ino for p_ in INO3[ino]["paths"])
truth = {"files": {}, "lost": lost_paths}
for p_, data in live3.items():
    truth["files"][p_] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
print(f"{len(truth['files'])} files, lost {len(lost_paths)}: {lost_paths}")
assert not (lost_ino & PROTECT), lost_ino & PROTECT
for need in ("jcopy_it_lost", "it_lost", "it_superseded", "ext_lost", "uninit", "data_lost"):
    assert tags.get(need), f"trap {need} missing"


# poison check: undetermined bytes filled with junk, recovered verbatim (no checksum
# shortcuts), every file read back with debugfs. kept files never move, lost ones do.
def replay_verbatim(buf):
    out = bytearray(buf)
    for fsb, (_seq, jl) in FSRC.items():
        pb = JOURNAL[jl]
        out[fsb * BS:(fsb + 1) * BS] = buf[pb * BS:(pb + 1) * BS]
    return out


ctl = replay_verbatim(DISKB)
badc = [x for x in range(1, NBLK) if x not in jset and x not in data4_new and blk(ctl, x) != blk(F3B, x)]
assert not badc, f"verbatim replay differs from F3 in {len(badc)} blocks, first {badc[:12]}"
moved = set()
for v in range(3):
    pr = random.Random(1000 + v)
    buf = bytearray(DISKB)
    for a in UND:
        buf[a * 512:(a + 1) * 512] = bytes(pr.getrandbits(8) for _ in range(512))
    img = f"{WORK}/poison{v}.img"
    with open(img, "wb") as f:
        f.write(replay_verbatim(buf))
    for i, p_ in enumerate(sorted(live3)):
        fn = f"{WORK}/pz{v}_{i}"
        try:
            subprocess.run(["debugfs", "-n", "-R", f'dump "{p_}" {fn}', img],
                           capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            pass
        got = rd(fn) if os.path.exists(fn) else None
        if got != live3[p_]:
            moved.add(p_)
        if os.path.exists(fn):
            os.remove(fn)
assert moved <= set(lost_paths), f"files that move but are not lost: {moved - set(lost_paths)}"
assert set(lost_paths) <= moved, f"lost files that never moved: {set(lost_paths) - moved}"
print("poison check: exactly the lost files move")

# ---------------------------------------------------------------- member images
E_NOW, E_X, E_DROP = 18742, 18740, 18690
UUID = bytes.fromhex("8c3f1e27a94b5d06b2e1c47f9035da6e")
DEV_UUID = {k: hashlib.md5(f"dev{k}{SEED}".encode()).digest() for k in range(N)}
CTIME = M.md_time(ts("2023-03-14 10:19"), 412000)
U_FAIL = M.md_time(ts("2026-09-30 01:17"), 233000)
U_X = M.md_time(ts("2026-09-30 01:17"), 4000)

members = {}
for k in range(N):
    data = bytearray(D2[k])
    if k == S_ROLE:
        data[R * 512:] = D0[k][R * 512:]
        for row in range(R, DATA_SECT):     # clean chunks above the front were never touched
            if (row // BM_SECT) not in dirty_set:
                assert D0[k][row * 512:(row + 1) * 512] == D2[k][row * 512:(row + 1) * 512]
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
                  chunksize=BM_CHUNK, sectors_reserved=DATA_OFF - 16, bits=dirty, nbits=NBITS)
    img[8 * 512:9 * 512] = sb[:512]
    img[16 * 512:16 * 512 + len(bm)] = bm
    members[k] = img
for k, img in members.items():
    with open(f"{CASE_OUT}/{BAY_OF_ROLE[k]}.img", "wb") as f:
        f.write(img)


# ---------------------------------------------------------------- ddrescue mapfiles
def mapfile(name, size, areas, finished, dev):
    lines, pos = [], 0
    for p_, s_, st in sorted(areas):
        if p_ > pos:
            lines.append((pos, p_ - pos, "+"))
        lines.append((p_, s_, st))
        pos = p_ + s_
    if pos < size:
        lines.append((pos, size - pos, "+"))
    if finished:
        cur, cst, cpass = (lines[-1][0], "+", 3)
        head_ = ["# Mapfile. Created by GNU ddrescue version 1.27",
                 f"# Command line: ddrescue -d -r3 {dev} {name}.img {name}.map",
                 "# Start time:   2026-10-01 09:14:02",
                 "# Current time: 2026-10-01 09:41:55",
                 "# Finished"]
    else:
        cur, cst, cpass = (max(areas)[0], "/", 1)
        head_ = ["# Mapfile. Created by GNU ddrescue version 1.27",
                 f"# Command line: ddrescue -d {dev} {name}.img {name}.map",
                 "# Start time:   2026-10-01 10:02:37",
                 "# Current time: 2026-10-01 13:26:10",
                 "# Scraping failed blocks... (forwards)",
                 "# Interrupted by user"]
    out = head_ + ["# current_pos  current_status  current_pass",
                   f"0x{cur:08X}     {cst}               {cpass}",
                   "#      pos        size  status"]
    out += [f"0x{p_:08X}  0x{s_:08X}  {st}" for p_, s_, st in lines]
    return "\n".join(out) + "\n"


DEVNODE = {"bay1": "/dev/sdb", "bay2": "/dev/sdc", "bay3": "/dev/sdd", "bay4": "/dev/sde"}
for k in range(N):
    name = BAY_OF_ROLE[k]
    areas = [((DATA_OFF + s0) * 512, ln * 512, st) for s0, ln, st in bad.get(k, [])]
    txt = mapfile(name, len(members[k]), areas, finished=(k != X_ROLE), dev=DEVNODE[name])
    with open(f"{CASE_OUT}/{name}.map", "w") as f:
        f.write(txt)

meta = {"R": R, "bad": {str(k): v for k, v in bad.items()}, "dirty": dirty, "tags": tags,
        "lost": lost_paths, "revoke_bite": bite, "seed": SEED,
        "txns": [(t_["seq"], len(t_["tags"]), t_["revokes"], t_["commit"]) for t_ in LOG]}
with open(f"{SEALED}/truth.json", "w") as f:
    json.dump(truth, f, indent=1, sort_keys=True)
with open(f"{SEALED}/gen_meta.json", "w") as f:
    json.dump(meta, f, indent=1)
shutil.copy(DISK, f"{SEALED}/disk.img")
print("done")
