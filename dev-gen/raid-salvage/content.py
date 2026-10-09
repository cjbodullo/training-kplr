"""deterministic file content for the share (authoring only)."""
import gzip
import io
import struct
import zlib

WORDS = """
site survey drawing revision client approval structural beam column slab footing
retaining wall drainage facade glazing cladding render timber steel concrete
schedule tender contractor invoice payment retention variation claim certificate
planning consent heritage officer neighbour boundary party wall easement access
lift stair landing corridor plant room roof parapet gutter downpipe membrane
insulation thermal acoustic fire stopping sprinkler compartment escape route
budget estimate quantity surveyor programme milestone handover snag defect
meeting minutes action owner deadline review comment markup issue status
loft harbour quay mill chapel terrace yard warehouse studio gallery annex
north south east west elevation section plan detail level grid datum
""".split()
NAMES = ["mara", "devin", "okafor", "priya", "ansel", "joss", "ilka", "tomas"]
FIRMS = ["Brindle Joinery", "Coldharbour Steel", "Fenwick Glazing", "Ashdown Civils",
         "Pellow Roofing", "Marrick Electrical", "Quarry Lane Plant Hire",
         "Halse Scaffolding", "Tidewater Surveys", "Orchard M&E"]


def sentence(r):
    n = r.randint(6, 18)
    w = [r.choice(WORDS) for _ in range(n)]
    w[0] = w[0].capitalize()
    return " ".join(w) + r.choice([".", ".", ".", "?", ";"])


def text_doc(r, nbytes, title):
    out = [f"# {title}", ""]
    size = 0
    while size < nbytes:
        para = " ".join(sentence(r) for _ in range(r.randint(2, 6)))
        out.append(para)
        out.append("")
        size += len(para) + 2
    return ("\n".join(out) + "\n").encode()


def ledger(r, rows, year, q):
    lines = ["date,ref,supplier,project,net,vat,gross,status"]
    for i in range(rows):
        m = (q - 1) * 3 + r.randint(1, 3)
        net = r.randint(1500, 2500000) / 100
        vat = round(net * 0.2, 2)
        lines.append(f"{year}-{m:02d}-{r.randint(1,28):02d},INV-{r.randint(10000,99999)},"
                     f"{r.choice(FIRMS)},P-{r.randint(2200,2320)},{net:.2f},{vat:.2f},"
                     f"{net+vat:.2f},{r.choice(['paid','paid','held','disputed','paid'])}")
    return ("\n".join(lines) + "\n").encode()


def logfile(r, lines, t0, svc):
    out = []
    t = t0
    for _ in range(lines):
        t += r.randint(1, 240)
        lvl = r.choice(["INFO"] * 8 + ["WARN", "ERROR"])
        msg = " ".join(r.choice(WORDS) for _ in range(r.randint(3, 9)))
        out.append(f"{t} {svc}[{r.randint(200, 9000)}]: {lvl} {msg} "
                   f"id={r.getrandbits(32):08x}")
    return ("\n".join(out) + "\n").encode(), t


def code(r, nfuncs):
    out = ["#!/usr/bin/env python3", "import csv", "import sys", ""]
    for i in range(nfuncs):
        a, b = r.choice(WORDS), r.choice(WORDS)
        out.append(f"def {a}_{b}_{i}(rows, limit={r.randint(1, 500)}):")
        out.append(f"    total = 0")
        out.append(f"    for row in rows:")
        out.append(f"        if row.get('{r.choice(WORDS)}') and total < limit:")
        out.append(f"            total += float(row['{r.choice(WORDS)}']) * {r.randint(1,9)}")
        out.append(f"    return total")
        out.append("")
    return ("\n".join(out) + "\n").encode()


def png(r, w, h, noise):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        base = (y * 255) // h
        for x in range(w):
            g = (base + (x * 128) // w) & 0xFF
            raw += bytes(((g + r.randint(0, noise)) & 0xFF,
                          (g // 2 + r.randint(0, noise)) & 0xFF,
                          (255 - g + r.randint(0, noise)) & 0xFF))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def gz(data, name):
    buf = io.BytesIO()
    with gzip.GzipFile(filename=name, mode="wb", fileobj=buf, mtime=0) as g:
        g.write(data)
    return buf.getvalue()
