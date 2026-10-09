"""ext4 introspection through debugfs 1.47.0 (authoring only).

model(img) -> dict with
  tree    {path: (ino, kind, size)}              kind in reg/dir
  inodes  {ino: {"kind", "size", "paths", "leaves": [(lblk, pblk, len, uninit)],
                 "tree": [pblk of index/leaf blocks]}}
  data    {pblk: (ino, lblk)}                    initialized file data blocks
  uninit  {pblk: (ino, lblk)}                    unwritten extent blocks
  dirblk  set of directory blocks
  extblk  {pblk: ino}                            extent index/leaf blocks
  journal [pblk of journal logical block 0..]
  geo     {"ipg", "isz", "it": [(start, nblocks)], "bb": [...], "ib": [...]}
"""
import re
import subprocess

EXT_RE = re.compile(r"^\s*(\d+)/\s*(\d+)\s+\d+/\s*\d+\s+(\d+)\s*-\s*(\d+)\s+(\d+)(?:\s*-\s*(\d+))?\s+(\d+)\s*(\S*)")


def _dbg_batch(img, cmds):
    """run debugfs -f over cmds, return list of outputs in order."""
    script = "\n".join(cmds) + "\n"
    p = subprocess.run(["debugfs", "-n", "-f", "-", img], input=script,
                       capture_output=True, text=True)
    outs, cur = [], None
    for ln in p.stdout.splitlines():
        if ln.startswith("debugfs: "):
            if cur is not None:
                outs.append("\n".join(cur))
            cur = []
            continue
        if cur is not None:
            cur.append(ln)
    if cur is not None:
        outs.append("\n".join(cur))
    assert len(outs) == len(cmds), (len(outs), len(cmds), p.stderr[-500:])
    return outs


def parse_ex(txt):
    leaves, tree = [], []
    for ln in txt.splitlines():
        m = EXT_RE.match(ln)
        if not m:
            continue
        lvl, maxl = int(m[1]), int(m[2])
        if lvl < maxl:
            tree.append(int(m[5]))
        else:
            leaves.append((int(m[3]), int(m[5]), int(m[7]), "Uninit" in (m[8] or "")))
    return leaves, tree


def geometry(img):
    p = subprocess.run(["dumpe2fs", img], capture_output=True, text=True)
    t = p.stdout
    geo = {"ipg": int(re.search(r"Inodes per group:\s+(\d+)", t)[1]),
           "isz": int(re.search(r"Inode size:\s+(\d+)", t)[1]),
           "bs": int(re.search(r"Block size:\s+(\d+)", t)[1]),
           "it": [], "bb": [], "ib": []}
    for m in re.finditer(r"Inode table at (\d+)-(\d+)", t):
        geo["it"].append((int(m[1]), int(m[2]) - int(m[1]) + 1))
    geo["bb"] = [int(x) for x in re.findall(r"Block bitmap at (\d+)", t)]
    geo["ib"] = [int(x) for x in re.findall(r"Inode bitmap at (\d+)", t)]
    return geo


def inode_loc(geo, ino):
    """-> (fs block, byte offset) of the on-disk inode."""
    g, idx = divmod(ino - 1, geo["ipg"])
    start, _n = geo["it"][g]
    b, off = divmod(idx * geo["isz"], geo["bs"])
    return start + b, off


def model(img):
    geo = geometry(img)
    tree, inodes = {}, {}
    level = ["/"]
    while level:
        outs = _dbg_batch(img, [f'ls -p "{d}"' for d in level])
        nxt = []
        for d, out in zip(level, outs):
            for ln in out.splitlines():
                m = re.match(r"^/(\d+)/(\d+)/\d+/\d+/([^/]*)/(\d*)/$", ln)
                if not m:
                    continue
                ino, mode, name, size = int(m[1]), int(m[2], 8), m[3], m[4]
                if name in (".", "..", "") or ino == 0:
                    continue
                path = d.rstrip("/") + "/" + name
                fmt = mode & 0o170000
                kind = {0o100000: "reg", 0o040000: "dir"}.get(fmt)
                if kind is None:
                    raise SystemExit(f"unexpected file type {path} {oct(mode)}")
                tree[path] = (ino, kind, int(size or 0))
                inodes.setdefault(ino, {"kind": kind, "size": int(size or 0), "paths": []})["paths"].append(path)
                if kind == "dir":
                    nxt.append(path)
        level = nxt
    inos = sorted(inodes) + [2, 8]
    outs = _dbg_batch(img, [f"ex <{i}>" for i in inos])
    data, uninit, dirblk, extblk = {}, {}, set(), {}
    journal = []
    root = {"kind": "dir", "size": 0, "paths": ["/"]}
    for ino, out in zip(inos, outs):
        leaves, tr = parse_ex(out)
        if ino == 8:
            for l0, p0, n, _u in sorted(leaves):
                assert l0 == len(journal)
                journal += list(range(p0, p0 + n))
            continue
        info = inodes[ino] if ino in inodes else inodes.setdefault(2, root)
        info["leaves"], info["tree"] = leaves, tr
        for pb in tr:
            extblk[pb] = ino
        for l0, p0, n, u in leaves:
            for k in range(n):
                if info["kind"] == "dir":
                    dirblk.add(p0 + k)
                elif u:
                    uninit[p0 + k] = (ino, l0 + k)
                else:
                    data[p0 + k] = (ino, l0 + k)
    return {"tree": tree, "inodes": inodes, "data": data, "uninit": uninit,
            "dirblk": dirblk, "extblk": extblk, "journal": journal, "geo": geo}


def metadata_blocks(m, nblocks):
    """blocks ext4 journals when they change: group descriptors, bitmaps, inode
    tables, directory blocks and extent tree blocks. file data and free space are
    written in place and never go through the log."""
    g = m["geo"]
    out = {1} | set(g["bb"]) | set(g["ib"]) | set(m["dirblk"]) | set(m["extblk"])
    for s0, n in g["it"]:
        out.update(range(s0, s0 + n))
    return {b for b in out if b < nblocks}
