#!/usr/bin/env python3
"""salvage the ext4 share off the tarn md raid5 member images.

usage: recover.py CASE_DIR OUT_DIR

reads only the evidence: the member images, their ddrescue mapfiles, what
mdadm 4.2 says about each superblock and bitmap, and what debugfs says about
the filesystem once the array is put back together.

1. md. per member sector row (device sector relative to the data offset) the
   unknown members are
     - every member whose mapfile says that sector was never read
       (any status other than '+': '-' bad, '/' non-scraped, '*' non-trimmed, '?')
     - the member that was being recovered, unless the row is below its recovery
       offset or its write intent bitmap chunk is clean
   no unknown: take the row as is. one unknown: it is the xor of the others.
   two or more: the data sectors of the unknown members are undetermined.
2. ext4 was never unmounted, so the share "as it was" is what journal recovery
   gives: every committed jbd2 transaction replayed in order, revoke records
   honoured, the uncommitted tail ignored. a replayed block takes its bytes, and
   its undetermined sectors, from its journal copy; the in place block no longer
   matters.
3. a regular file is fully determined iff its own 256 byte inode, every extent
   index/leaf block of its tree, and every initialized data byte below i_size are
   determined. unwritten extents and holes read as zeros whatever is on disk.
   names and file types come from the directory entries, which stay readable even
   when an inode does not.

RS_MODE switches to wrong readings, for ablations only:
  force       every member taken as current, unread areas used as read
  degraded    the recovering member dropped entirely
  bitmap      recovering member current only in clean chunks (offset ignored)
  offset      recovering member current only below its offset (bitmap ignored)
  dashonly    only '-' counts as unread
  noreplay    the journal is ignored, files read as they sit in place
  norevoke    revoke records ignored during replay
  uncommitted the uncommitted tail transaction is replayed too
  oldcopy     an undetermined journal copy is skipped and the in place block kept
              (what e2fsck does when a tag checksum fails)
  wholeblock  an undetermined sector of an inode table loses the whole 4 KiB block
  uninit      unwritten extents treated as data
  noext       extent tree blocks ignored
  noinode     an undetermined inode is read as whatever the image holds
  inplace     in place losses still count after a journal copy replaced the block
  norehab     the recovering member is never trusted in a dirty chunk above its offset
  mtime       blocks of files with an old mtime (not ctime) trusted on the recovering member
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile

CASE, OUT = sys.argv[1], sys.argv[2]
MODE = os.environ.get("RS_MODE", "ref")
WORK = "/tmp/salvage"
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
os.makedirs(OUT, exist_ok=True)


def run(cmd, inp=None):
    p = subprocess.run(cmd, capture_output=True, text=True, input=inp)
    if p.returncode != 0:
        raise SystemExit(f"{cmd}: rc {p.returncode}\n{p.stdout}\n{p.stderr}")
    return p.stdout


def field(txt, name):
    m = re.search(r"^\s*" + re.escape(name) + r" : (.*)$", txt, re.M)
    return m.group(1).strip() if m else None


def sectors(v):
    return int(v.split()[0])


# ------------------------------------------------------------- superblocks
members = {}
for fn in sorted(os.listdir(CASE)):
    if not fn.endswith(".img"):
        continue
    path = os.path.join(CASE, fn)
    ex = run(["mdadm", "--examine", path])
    if "Checksum" not in ex or "correct" not in field(ex, "Checksum"):
        raise SystemExit(f"{fn}: superblock checksum not correct")
    role = field(ex, "Device Role")
    m = re.match(r"Active device (\d+)", role)
    if not m:
        raise SystemExit(f"{fn}: role {role}")
    members[int(m[1])] = {
        "name": fn[:-4], "path": path, "ex": ex,
        "uuid": field(ex, "Array UUID"),
        "level": field(ex, "Raid Level"),
        "ndev": int(field(ex, "Raid Devices")),
        "layout": field(ex, "Layout"),
        "chunk": int(field(ex, "Chunk Size").rstrip("K")) * 2,
        "data_off": sectors(field(ex, "Data Offset")),
        "super_off": sectors(field(ex, "Super Offset")),
        "avail": sectors(field(ex, "Avail Dev Size")),
        "events": int(field(ex, "Events")),
        "rec_off": sectors(field(ex, "Recovery Offset")) if field(ex, "Recovery Offset") else None,
        "bm_off": sectors(field(ex, "Internal Bitmap").split(" sectors")[0]) if field(ex, "Internal Bitmap") else None,
    }
N = len(members)
ref = members[0]
for k, m in members.items():
    assert m["uuid"] == ref["uuid"] and m["ndev"] == N, k
    assert m["level"] == "raid5" and m["layout"] == "left-symmetric", m
    assert m["chunk"] == ref["chunk"] and m["data_off"] == ref["data_off"]
CHUNK = ref["chunk"]
DATA = ref["avail"]
recovering = [k for k, m in members.items() if m["rec_off"] is not None]
assert len(recovering) == 1, recovering
S = recovering[0]
R = members[S]["rec_off"]
for k, m in sorted(members.items()):
    print(f"role {k}: {m['name']} events {m['events']} rec_off {m['rec_off']}", file=sys.stderr)

# ------------------------------------------------------------- bitmap
# mdadm -X on a plain file reads it as an external bitmap file, so cut the internal
# bitmap out first. take it from a member that is current and not recovering.
src = max((k for k in members if k != S), key=lambda k: members[k]["events"])
m = members[src]
bm_start = (m["super_off"] + m["bm_off"]) * 512
with open(m["path"], "rb") as f:
    f.seek(bm_start)
    bm_raw = f.read((m["data_off"] - m["super_off"] - m["bm_off"]) * 512)
with open(WORK + "/bitmap", "wb") as f:
    f.write(bm_raw)
xb = run(["mdadm", "--examine-bitmap", WORK + "/bitmap"])
bm_chunk = int(field(xb, "Chunksize").split()[0]) * {"KB": 1024, "MB": 1 << 20, "B": 1}[field(xb, "Chunksize").split()[1]]
sync_kib = int(field(xb, "Sync Size").split()[0])
nbits = int(field(xb, "Bitmap").split()[0])
assert sync_kib * 2 == DATA, (sync_kib, DATA)
assert field(xb, "UUID").replace(":", "") == ref["uuid"].replace(":", "")
BM_SECT = bm_chunk // 512
bits = bm_raw[256:256 + (nbits + 7) // 8]


def dirty(row):
    b = row // BM_SECT
    return bool(bits[b // 8] >> (b % 8) & 1)


# ------------------------------------------------------------- mapfiles
types = "-" if MODE == "dashonly" else "?*/-"
unread = {k: set() for k in members}
for k, m in members.items():
    out = run(["ddrescuelog", "-b512", f"--list-blocks={types}",
               os.path.join(CASE, m["name"] + ".map")])
    for ln in out.split():
        s = int(ln) - m["data_off"]
        if 0 <= s < DATA:
            unread[k].add(s)
        elif s < 0:
            raise SystemExit(f"{m['name']}: unread metadata sector {ln}")
    print(f"{m['name']}: {len(unread[k])} unread data sectors", file=sys.stderr)


def s_current(row, trust=frozenset()):
    if row in trust:
        return True
    if MODE == "force":
        return True
    if MODE == "degraded":
        return False
    if MODE == "bitmap":
        return not dirty(row)
    if MODE == "offset":
        return row < R
    return row < R or not dirty(row)


# ------------------------------------------------------------- reassemble
IMGS = {}
for k, m in members.items():
    with open(m["path"], "rb") as f:
        f.seek(m["data_off"] * 512)
        IMGS[k] = f.read(DATA * 512)
CH = CHUNK * 512


def xor(blobs):
    v = 0
    for b in blobs:
        v ^= int.from_bytes(b, "little")
    return v.to_bytes(len(blobs[0]), "little")


def data_loc(k, row):
    s_, within = divmod(row, CHUNK)
    pd = (N - 1) - (s_ % N)
    if k == pd:
        return None
    return ((s_ * (N - 1) + (k - pd - 1) % N) * CHUNK + within) * 512


def reconstruct(trust):
    """trust: member rows where the recovering member is provably current although the
    bitmap calls its chunk dirty. -> (array image, undetermined 512 byte sectors)"""
    array = bytearray((N - 1) * DATA * 512)
    undet = set()
    for s_ in range(DATA // CHUNK):
        pd = (N - 1) - (s_ % N)
        unk = []
        for row in range(s_ * CHUNK, (s_ + 1) * CHUNK):
            u = set() if MODE == "force" else {k for k in members if row in unread[k]}
            if not s_current(row, trust):
                u.add(S)
            unk.append(frozenset(u))
        col = {k: bytearray(IMGS[k][s_ * CH:(s_ + 1) * CH]) for k in members}
        i = 0
        while i < CHUNK:
            j = i
            while j < CHUNK and unk[j] == unk[i]:
                j += 1
            u = unk[i]
            a, b = i * 512, j * 512
            if len(u) == 1:
                (k,) = u
                col[k][a:b] = xor([col[o][a:b] for o in members if o != k])
            elif len(u) >= 2:
                for k in u:
                    col[k][a:b] = bytes(b - a)
                    if k != pd:
                        di = (k - pd - 1) % N
                        base = (s_ * (N - 1) + di) * CH
                        undet.update(range((base + a) // 512, (base + b) // 512))
            i = j
        for di in range(N - 1):
            k = (pd + 1 + di) % N
            c = s_ * (N - 1) + di
            array[c * CH:(c + 1) * CH] = col[k]
    return array, undet


EXT_RE = re.compile(r"^\s*(\d+)/\s*(\d+)\s+\d+/\s*\d+\s+(\d+)\s*-\s*(\d+)\s+(\d+)(?:\s*-\s*(\d+))?\s+(\d+)\s*(\S*)")


def extents(img, ino):
    leaves, tree = [], []
    for ln in run(["debugfs", "-n", "-R", f"ex <{ino}>", img]).splitlines():
        mm = EXT_RE.match(ln)
        if not mm:
            continue
        if int(mm[1]) < int(mm[2]):
            tree.append(int(mm[5]))
        else:
            leaves.append((int(mm[3]), int(mm[5]), int(mm[7]), "Uninit" in (mm[8] or "")))
    return leaves, tree


def analyze(array, undet, tag):
    """journal recovery + file determinability on one reconstruction."""
    AIMG = f"{WORK}/array-{tag}.img"
    with open(AIMG, "wb") as f:
        f.write(array)
    # dumpe2fs gives up on a bitmap whose checksum fails (a lost bitmap sector is
    # harmless for file contents), debugfs -n reads the descriptors without checking
    dump = run(["debugfs", "-n", "-R", "stats", AIMG])
    BS = int(re.search(r"Block size:\s+(\d+)", dump)[1])
    SPB = BS // 512
    IPG = int(re.search(r"Inodes per group:\s+(\d+)", dump)[1])
    ISZ = int(re.search(r"Inode size:\s+(\d+)", dump)[1])
    ITAB = [int(x) for x in re.findall(r"inode table at (\d+)", dump)]

    # ---- journal
    journal = []
    for l0, p0, n, _u in sorted(extents(AIMG, 8)[0]):
        assert l0 == len(journal)
        journal += list(range(p0, p0 + n))
    txns, cur = {}, None
    for ln in run(["debugfs", "-n", "-R", "logdump -a", AIMG]).splitlines():
        mm = re.match(r"Found expected sequence (\d+), type (\d+) \((.*)\) at block (\d+)", ln)
        if mm:
            cur = txns.setdefault(int(mm[1]), {"seq": int(mm[1]), "tags": [], "revokes": [],
                                               "commit": False, "struct": []})
            cur["struct"].append(int(mm[4]))
            if mm[2] == "2":
                cur["commit"] = True
            continue
        mm = re.match(r"\s+FS block (\d+) logged at journal block (\d+) \(flags (0x[0-9a-f]+)\)", ln)
        if mm:
            if int(mm[3], 16) & 1:
                raise SystemExit("escaped journal block, restore the magic before replay")
            cur["tags"].append((int(mm[1]), int(mm[2])))
            continue
        mm = re.match(r"\s+Revoke FS block (\d+)", ln)
        if mm:
            cur["revokes"].append(int(mm[1]))
    log = [txns[k] for k in sorted(txns)]
    for t in log:
        print(f"[{tag}] txn {t['seq']}: {len(t['tags'])} blocks, {len(t['revokes'])} revokes, "
              f"{'committed' if t['commit'] else 'NOT committed'}", file=sys.stderr)
        for jb in t["struct"] + [0]:
            if any(journal[jb] * SPB + i in undet for i in range(SPB)):
                raise SystemExit(f"journal structure block {jb} undetermined")
    use = [t for t in log if t["commit"] or MODE == "uncommitted"]
    revs = {}
    if MODE != "norevoke":
        for t in use:
            for b in t["revokes"]:
                revs[b] = max(revs.get(b, 0), t["seq"])
    final = {}
    for t in use:
        for fsb, jl in t["tags"]:
            if revs.get(fsb, 0) < t["seq"]:
                final[fsb] = journal[jl]
    if MODE == "noreplay":
        final = {}

    def sect_undet(b):
        return {i for i in range(SPB) if b * SPB + i in undet}

    rep = bytearray(array)
    fundet = {}
    for b in {s_ // SPB for s_ in undet}:
        if b not in final:
            fundet[b] = sect_undet(b)
    for fsb, pb in final.items():
        us = sect_undet(pb)
        if us and MODE == "oldcopy":
            continue          # e2fsck: tag checksum fails, keep what is in place
        rep[fsb * BS:(fsb + 1) * BS] = array[pb * BS:(pb + 1) * BS]
        if MODE == "inplace":
            us = us | sect_undet(fsb)
        if us:
            fundet[fsb] = us
        else:
            fundet.pop(fsb, None)
    fundet = {b: v for b, v in fundet.items() if v}
    RIMG = f"{WORK}/recovered-{tag}.img"
    with open(RIMG, "wb") as f:
        f.write(rep)

    def blk_undet(b):
        return bool(fundet.get(b))

    def inode_undet(ino, any_mode=False):
        if MODE == "noinode" and not any_mode:
            return False
        g, idx = divmod(ino - 1, IPG)
        b, off = divmod(idx * ISZ, BS)
        us = fundet.get(ITAB[g] + b, set())
        if MODE == "wholeblock":
            return bool(us)
        return any(i in us for i in range(off // 512, (off + ISZ - 1) // 512 + 1))

    # ---- directory tree, from the directory blocks themselves: an entry's file type
    # survives a lost inode
    def dir_entries(ino):
        if inode_undet(ino, True):
            raise SystemExit(f"directory inode {ino} undetermined")
        leaves, tree = extents(RIMG, ino)
        if any(blk_undet(b) for b in tree):
            raise SystemExit(f"directory {ino} extent block undetermined")
        out = []
        for l0, p0, n, _u in leaves:
            for b in range(p0, p0 + n):
                if blk_undet(b):
                    raise SystemExit(f"directory {ino} block {b} undetermined")
                data = rep[b * BS:(b + 1) * BS]
                pos = 0
                while pos < BS:
                    dino, rlen, nlen, ftype = struct.unpack_from("<IHBB", data, pos)
                    if rlen < 8:
                        break
                    if dino and nlen:
                        out.append((data[pos + 8:pos + 8 + nlen].decode("utf-8", "surrogateescape"), dino, ftype))
                    pos += rlen
        return out

    files = {}
    todo = [(2, "")]
    while todo:
        dino, dpath = todo.pop()
        for name, ino, ftype in dir_entries(dino):
            if name in (".", ".."):
                continue
            p = dpath + "/" + name
            if ftype == 2:
                if p != "/lost+found":
                    todo.append((ino, p))
            elif ftype == 1:
                files.setdefault(ino, []).append(p)
            else:
                raise SystemExit(f"unexpected file type {ftype} at {p}")

    # ---- which files are pinned down. for every file whose inode and extent tree are
    # determined we also keep its times and blocks: they prove which blocks have not
    # changed since the member dropped out.
    lost, keep, known = set(), [], {}
    for ino, paths in sorted(files.items()):
        if inode_undet(ino):
            lost.update(paths)
            continue
        st = run(["debugfs", "-n", "-R", f"stat <{ino}>", RIMG])
        size = int(re.search(r"Size: (\d+)", st)[1])
        leaves, tree = extents(RIMG, ino)
        tree_bad = any(blk_undet(b) for b in tree)
        if not tree_bad:
            known[ino] = {"ctime": int(re.search(r"ctime: 0x([0-9a-f]+)", st)[1], 16),
                          "mtime": int(re.search(r"mtime: 0x([0-9a-f]+)", st)[1], 16),
                          "blocks": [p0 + k for _l, p0, n, _u in leaves for k in range(n)]}
        bad = MODE != "noext" and tree_bad
        for l0, p0, n, uninit in leaves:
            if uninit and MODE != "uninit":
                continue
            for k in range(n):
                for i in fundet.get(p0 + k, ()):
                    if (l0 + k) * BS + i * 512 < size:
                        bad = True
        if bad:
            lost.update(paths)
        else:
            keep += [(p, ino) for p in paths]
    return {"files": files, "lost": lost, "keep": keep, "known": known, "img": RIMG, "BS": BS}


def drop_time(res):
    """when the recovering member fell out, from the kernel log on the share."""
    import calendar
    import time
    for p, ino in res["keep"]:
        if not p.endswith(".log"):
            continue
        out = WORK + "/klog"
        run(["debugfs", "-n", "-R", f"dump <{ino}> {out}", res["img"]])
        txt = open(out, "rb").read().decode("utf-8", "replace")
        hits = re.findall(r"^(\w{3} [ \d]\d \d\d:\d\d:\d\d) \S+ kernel: .*md/raid:md\d+: Disk failure on", txt, re.M)
        if hits:
            year = time.gmtime(res["known"][ino]["mtime"]).tm_year
            t = calendar.timegm(time.strptime(f"{year} {hits[0]}", "%Y %b %d %H:%M:%S"))
            print(f"drop logged in {p}: {hits[0]} (local time, zone unknown)", file=sys.stderr)
            return t
    raise SystemExit("no record of the member dropping out")


def rehab_rows(res, t_drop):
    """rows above the front in dirty chunks where the recovering member is provably
    current: its sector (or, for parity, every data sector of the row) lies in a block
    of a file whose ctime is a day or more before the drop. a day of margin covers the
    log's unknown time zone and any writeback delay."""
    key = "mtime" if MODE == "mtime" else "ctime"
    old = {b for i in res["known"].values() if i[key] < t_drop - 86400 for b in i["blocks"]}
    bs = res["BS"]
    out = set()
    for row in range(R, DATA):
        if not dirty(row):
            continue
        a = data_loc(S, row)
        if a is not None:
            ok = a // bs in old
        else:
            ok = all(data_loc(k, row) // bs in old for k in members if k != S)
        if ok:
            out.add(row)
    return out


trust, it = frozenset(), 0
while True:
    array, undet = reconstruct(trust)
    res = analyze(array, undet, str(it))
    print(f"pass {it}: {len(undet)} undetermined sectors, {len(res['keep'])} kept, {len(res['lost'])} lost",
          file=sys.stderr)
    if MODE in ("force", "degraded", "bitmap", "offset", "norehab"):
        break
    new = frozenset(rehab_rows(res, drop_time(res)))
    if new == trust:
        break
    trust, it = new, it + 1
del IMGS

DUMP = WORK + "/files"
os.makedirs(DUMP)
cmds = [f'dump <{ino}> "{DUMP}/{ino}"' for ino in sorted({i for _, i in res["keep"]})]
run(["debugfs", "-n", "-f", "-", res["img"]], inp="\n".join(cmds) + "\n")
with tarfile.open(os.path.join(OUT, "recovered.tar"), "w", format=tarfile.GNU_FORMAT) as t:
    for p, ino in sorted(res["keep"]):
        t.add(f"{DUMP}/{ino}", arcname=p.lstrip("/"), recursive=False)
with open(os.path.join(OUT, "lost.txt"), "w") as f:
    for p in sorted(res["lost"]):
        f.write(p + "\n")
print(f"{len(res['keep'])} files recovered, {len(res['lost'])} lost", file=sys.stderr)
