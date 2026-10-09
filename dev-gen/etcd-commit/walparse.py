"""parse `etcd-dump-logs` text output (etcd 3.5.17) into python dicts."""
import re, subprocess

def unescape(s):
    out = bytearray(); i = 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out += ch.encode(); i += 1; continue
        n = s[i + 1]
        if n in "01234567":
            j = i + 1
            while j < len(s) and j < i + 4 and s[j] in "01234567": j += 1
            out.append(int(s[i + 1:j], 8)); i = j; continue
        if n == "x":
            out.append(int(s[i + 2:i + 4], 16)); i += 4; continue
        out += {"n": b"\n", "t": b"\t", "r": b"\r", '"': b'"', "'": b"'", "\\": b"\\"}[n]; i += 2
    return bytes(out)

TOK = re.compile(r'\s*(?:(?P<str>"(?:[^"\\]|\\.)*")|(?P<id>[A-Za-z_][A-Za-z0-9_]*)|(?P<num>-?\d+)|(?P<p>[:<>{}]))')

def parse_text(s):
    toks = []; pos = 0
    while pos < len(s):
        if s[pos:].strip() == "": break
        m = TOK.match(s, pos)
        if not m: raise ValueError("bad token at %r" % s[pos:pos + 30])
        pos = m.end()
        for k in ("str", "id", "num", "p"):
            if m.group(k) is not None: toks.append((k, m.group(k))); break
    i = 0
    def msg(end):
        nonlocal i
        d = {}
        while i < len(toks) and toks[i] != ("p", end):
            k, name = toks[i]; i += 1
            if toks[i] == ("p", ":"): i += 1
            if toks[i][0] == "p" and toks[i][1] in "<{":
                close = ">" if toks[i][1] == "<" else "}"; i += 1
                v = msg(close); i += 1
            else:
                t, v = toks[i]; i += 1
                if t == "str": v = unescape(v[1:-1])
                elif t == "num": v = int(v)
            d.setdefault(name, []).append(v)
        return d
    return msg(None)

LINE = re.compile(r"^\s+(\d+)\s+(\d+)\s+(norm|conf)\t(.*)$")

def dump(datadir, image="etcdgen", local=False):
    cmd = ["etcd-dump-logs", "--start-index", "1", datadir]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    meta = re.search(r"nodeID=(\w+) clusterID=(\w+) term=(\d+) commitIndex=(\d+) vote=(\w+)", out)
    ents = []
    for line in out.splitlines():
        m = LINE.match(line)
        if not m: continue
        term, index, typ, data = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
        req = None
        if typ == "norm" and data.startswith("header:"):
            req = parse_text(data)
        ents.append({"term": term, "index": index, "type": typ, "raw": data, "req": req})
    hs = {"node": meta.group(1), "term": int(meta.group(3)), "commit": int(meta.group(4)), "vote": meta.group(5)}
    return hs, ents
