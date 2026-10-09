#!/usr/bin/env python3
"""Fanuc 0i-MF milling interpreter (the subset these programs use) -> tool tip moves in machine coords.

Reads the control backups: ALL-PROG.TXT (punch), CNC-PARA.TXT, TOOLOFST.TXT (memory C, G10 L10-13),
EXT_WKZ.TXT (G10 L2 P0-6). Executes custom macro B and emits every move of the tool tip as the
machine makes it.

Semantics followed (Fanuc 0i-MF operator/programming manual):
  * 3401#0 DPI = 0: an axis address written without a decimal point is in least input increment
    (0.001 mm). values coming from variables or [expressions] are taken as mm.
  * work coordinate = G54..G59 + EXT (P0) ; G52 sets (replaces) a local shift ; G10 L2 in G90
    overwrites the given axes only.
  * G43 Hn adds H geometry + H wear ; the tip ends at Zcmd + (Hn - real length of the loaded tool).
  * G41/G42 Dn use D geometry + D wear ; start-up / cancel type A (5003#0 SUP = 0).
  * I/J are always incremental from the arc start ; R < 0 -> arc over 180 deg.
  * G51.1 mirror: the path is mirrored, so arc direction and offset side reverse.
  * G68 rotates programmed coordinates (incremental ones too) about the given centre.
  * canned cycles: G91 R is from the initial level, Z from the R point, K repeats.
  * M98 runs in the caller's local variable level, G65 opens a new one with arguments.
  * a vacant variable in an address omits that address.
  * modal state (G90/G91, G52, cycle data ...) survives M99.
"""
import math
import re

AXIS_SCALED = set("XYZIJRQ")    # addresses that read 1 = 0.001 mm without a decimal point (K here is a repeat count)
ARG_MAP = {"A": 1, "B": 2, "C": 3, "I": 4, "J": 5, "K": 6, "D": 7, "E": 8, "F": 9, "H": 11,
           "M": 13, "Q": 17, "R": 18, "S": 19, "T": 20, "U": 21, "V": 22, "W": 23,
           "X": 24, "Y": 25, "Z": 26}
EPS = 1e-9


class NCError(Exception):
    pass


# ----------------------------------------------------------------------------------- backups
def read_params(path):
    p = {}
    for line in open(path):
        m = re.match(r"N(\d+)Q1(.*)", line.strip())
        if not m:
            continue
        p[int(m.group(1))] = m.group(2)
    return p


def param_bit(params, no, bit):
    v = params.get(no, "P00000000")
    m = re.match(r"P([01]{8})$", v)
    if not m:
        raise NCError(f"parameter {no} not bit type")
    return int(m.group(1)[7 - bit])


def read_g10(path):
    """returns list of dicts of the G10 lines"""
    out = []
    for line in open(path):
        line = line.strip()
        if not line.startswith("G10"):
            continue
        words = dict((a, float(v)) for a, v in re.findall(r"([A-Z])(-?[\d.]+)", line[3:]))
        out.append(words)
    return out


def read_offsets(path):
    off = {"Hg": {}, "Hw": {}, "Dg": {}, "Dw": {}}
    key = {10: "Hg", 11: "Hw", 12: "Dg", 13: "Dw"}
    for w in read_g10(path):
        off[key[int(w["L"])]][int(w["P"])] = w["R"]
    return off


def read_work(path):
    wk = {}
    for w in read_g10(path):
        wk[int(w["P"])] = [w.get("X", 0.0), w.get("Y", 0.0), w.get("Z", 0.0)]
    return wk


# ----------------------------------------------------------------------------------- program store
def load_programs(path):
    text = open(path).read().replace("%", "")
    progs, cur = {}, None
    for raw in text.splitlines():
        line = re.sub(r"\([^)]*\)", "", raw).strip().upper()
        m = re.match(r"^O(\d+)", line)
        if m:
            cur = int(m.group(1))
            progs[cur] = []
            line = line[m.end():].strip()
        if cur is None or not line:
            continue
        progs[cur].append(line)
    return progs


# ----------------------------------------------------------------------------------- expressions
TOK = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)|(EQ|NE|GT|GE|LT|LE|AND|OR|XOR|MOD|SIN|COS|TAN|ATAN|SQRT|ABS|"
                 r"ROUND|FIX|FUP)|([#\[\]+\-*/]))")


def tokenize(s):
    out, i = [], 0
    s = s.strip()
    while i < len(s):
        m = TOK.match(s, i)
        if not m or m.end() == i:
            raise NCError(f"cannot tokenize {s[i:]!r}")
        out.append(m.group(1) or m.group(2) or m.group(3))
        i = m.end()
        while i < len(s) and s[i] == " ":
            i += 1
    return out


class Expr:
    def __init__(self, interp, toks):
        self.I, self.t, self.i = interp, toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self, want=None):
        tok = self.peek()
        if want is not None and tok != want:
            raise NCError(f"expected {want} got {tok} in {' '.join(self.t)}")
        self.i += 1
        return tok

    def cond(self):
        a = self.expr()
        op = self.peek()
        if op in ("EQ", "NE", "GT", "GE", "LT", "LE"):
            self.take()
            b = self.expr()
            if op in ("EQ", "NE"):
                if a is None or b is None:
                    r = (a is None and b is None)
                else:
                    r = abs(a - b) < 1e-9
                return r if op == "EQ" else not r
            a = 0.0 if a is None else a
            b = 0.0 if b is None else b
            return {"GT": a > b, "GE": a >= b, "LT": a < b, "LE": a <= b}[op]
        return a

    def expr(self):
        v = self.term()
        while self.peek() in ("+", "-", "OR", "XOR"):
            op = self.take()
            w = self.term()
            v, w = (v or 0.0), (w or 0.0)
            v = v + w if op == "+" else v - w if op == "-" else float(int(v) | int(w)) if op == "OR" \
                else float(int(v) ^ int(w))
        return v

    def term(self):
        v = self.factor()
        while self.peek() in ("*", "/", "AND", "MOD"):
            op = self.take()
            w = self.factor()
            v, w = (v or 0.0), (w or 0.0)
            if op == "*":
                v = v * w
            elif op == "/":
                v = v / w
            elif op == "AND":
                v = float(int(v) & int(w))
            else:
                v = math.fmod(v, w)
        return v

    def factor(self):
        tok = self.peek()
        if tok == "-":
            self.take()
            v = self.factor()
            return None if v is None else -v
        if tok == "+":
            self.take()
            return self.factor()
        if tok == "[":
            self.take()
            v = self.expr()
            self.take("]")
            return v
        if tok == "#":
            self.take()
            n = self.factor()
            return self.I.getvar(int(round(n)))
        if tok in ("SIN", "COS", "TAN", "SQRT", "ABS", "ROUND", "FIX", "FUP", "ATAN"):
            self.take()
            self.take("[")
            v = self.expr() or 0.0
            self.take("]")
            if tok == "SIN":
                return math.sin(math.radians(v))
            if tok == "COS":
                return math.cos(math.radians(v))
            if tok == "TAN":
                return math.tan(math.radians(v))
            if tok == "SQRT":
                return math.sqrt(v)
            if tok == "ABS":
                return abs(v)
            if tok == "ROUND":
                return math.floor(abs(v) + 0.5) * (1 if v >= 0 else -1)
            if tok == "FIX":
                return float(math.trunc(v))
            if tok == "FUP":
                return float(math.trunc(v) + (0 if v == math.trunc(v) else (1 if v > 0 else -1)))
            raise NCError("ATAN not supported")
        if tok is None:
            raise NCError("unexpected end of expression")
        self.take()
        return float(tok)


# ----------------------------------------------------------------------------------- geometry helpers
def rot(v, deg):
    a = math.radians(deg)
    return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a))


def arc_center(p0, p1, r, ccw):
    """centre of the arc p0->p1 with radius R (negative: more than 180 deg)"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    d = math.hypot(dx, dy)
    rr = abs(r)
    if d > 2 * rr + 1e-6:
        raise NCError("arc radius too small")
    h = math.sqrt(max(rr * rr - d * d / 4, 0.0))
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    nx, ny = -dy / d, dx / d          # left normal of chord
    # minor arc ccw -> centre on the left of the chord
    side = 1 if ccw else -1
    if r < 0:
        side = -side
    return (mx + side * h * nx, my + side * h * ny)


class Seg:
    """planar XY path element in program coordinates at height z"""

    def __init__(self, kind, p0, p1, z, center=None, ccw=None):
        self.kind, self.p0, self.p1, self.z, self.c, self.ccw = kind, p0, p1, z, center, ccw

    def radius(self):
        return math.hypot(self.p0[0] - self.c[0], self.p0[1] - self.c[1])

    def tangent(self, at_end):
        if self.kind == "L":
            dx, dy = self.p1[0] - self.p0[0], self.p1[1] - self.p0[1]
            n = math.hypot(dx, dy)
            return (dx / n, dy / n)
        p = self.p1 if at_end else self.p0
        rx, ry = p[0] - self.c[0], p[1] - self.c[1]
        n = math.hypot(rx, ry)
        return (-ry / n, rx / n) if self.ccw else (ry / n, -rx / n)


def left(t):
    return (-t[1], t[0])


def offset_seg(s, d, side):
    """offset a segment by d to the left (side=+1) or right (side=-1)"""
    if s.kind == "L":
        n = left(s.tangent(False))
        o = (n[0] * d * side, n[1] * d * side)
        return Seg("L", (s.p0[0] + o[0], s.p0[1] + o[1]), (s.p1[0] + o[0], s.p1[1] + o[1]), s.z)
    r = s.radius()
    # left of a ccw arc is the inside
    inward = (1 if s.ccw else -1) * side
    nr = r - inward * d
    if nr <= 1e-9:
        raise NCError("offset arc radius not positive (interference)")
    def mv(p):
        rx, ry = p[0] - s.c[0], p[1] - s.c[1]
        k = nr / math.hypot(rx, ry)
        return (s.c[0] + rx * k, s.c[1] + ry * k)
    return Seg("A", mv(s.p0), mv(s.p1), s.z, s.c, s.ccw)


def intersect(a, b, near):
    """intersection of offset elements a and b (as infinite line / full circle) nearest to `near`"""
    pts = []
    if a.kind == "L" and b.kind == "L":
        d1 = (a.p1[0] - a.p0[0], a.p1[1] - a.p0[1])
        d2 = (b.p1[0] - b.p0[0], b.p1[1] - b.p0[1])
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-12:
            return None
        t = ((b.p0[0] - a.p0[0]) * d2[1] - (b.p0[1] - a.p0[1]) * d2[0]) / den
        return (a.p0[0] + t * d1[0], a.p0[1] + t * d1[1])
    if a.kind == "A" and b.kind == "A":
        c1, r1, c2, r2 = a.c, a.radius(), b.c, b.radius()
        dx, dy = c2[0] - c1[0], c2[1] - c1[1]
        d = math.hypot(dx, dy)
        if d < 1e-12:
            return None
        x = (d * d + r1 * r1 - r2 * r2) / (2 * d)
        h2 = r1 * r1 - x * x
        if h2 < -1e-9:
            return None
        h = math.sqrt(max(h2, 0))
        bx, by = c1[0] + x * dx / d, c1[1] + x * dy / d
        pts = [(bx - h * dy / d, by + h * dx / d), (bx + h * dy / d, by - h * dx / d)]
    else:
        ln, ar = (a, b) if a.kind == "L" else (b, a)
        d = (ln.p1[0] - ln.p0[0], ln.p1[1] - ln.p0[1])
        n = math.hypot(*d)
        d = (d[0] / n, d[1] / n)
        f = (ln.p0[0] - ar.c[0], ln.p0[1] - ar.c[1])
        bq = f[0] * d[0] + f[1] * d[1]
        cq = f[0] ** 2 + f[1] ** 2 - ar.radius() ** 2
        disc = bq * bq - cq
        if disc < -1e-9:
            return None
        sq = math.sqrt(max(disc, 0))
        pts = [(ln.p0[0] + (-bq + s) * d[0], ln.p0[1] + (-bq + s) * d[1]) for s in (sq, -sq)]
    return min(pts, key=lambda p: math.hypot(p[0] - near[0], p[1] - near[1]))


def comp_path(start, segs, end, d, side):
    """type A start-up / cancel cutter compensation. returns list of Seg for the tool centre."""
    if d < 1e-12:
        out, cur = [], start
        for s in segs:
            out.append(s)
        return [Seg("L", start, segs[0].p0, segs[0].z)] + out + [Seg("L", segs[-1].p1, end, segs[-1].z)]
    offs = [offset_seg(s, d, side) for s in segs]
    # junctions
    pts_start = [o.p0 for o in offs]
    pts_end = [o.p1 for o in offs]
    path = []
    out_segs = [Seg(o.kind, o.p0, o.p1, o.z, o.c, o.ccw) for o in offs]
    inserts = {}
    for k in range(len(segs) - 1):
        t1 = segs[k].tangent(True)
        t2 = segs[k + 1].tangent(False)
        cross = t1[0] * t2[1] - t1[1] * t2[0]
        dot = t1[0] * t2[0] + t1[1] * t2[1]
        if abs(cross) < 1e-9 and dot > 0:
            continue                                   # tangent, offsets meet
        inner = cross * side > 0
        if inner:
            p = intersect(out_segs[k], out_segs[k + 1], segs[k].p1)
            if p is None:
                raise NCError("no intersection at inner corner")
            out_segs[k].p1 = p
            out_segs[k + 1].p0 = p
        else:
            corner = segs[k].p1
            inserts[k] = Seg("A", out_segs[k].p1, out_segs[k + 1].p0, segs[k].z, corner, side < 0)
    for k, s in enumerate(out_segs):
        path.append(s)
        if k in inserts:
            path.append(inserts[k])
    path.insert(0, Seg("L", start, out_segs[0].p0, segs[0].z))
    path.append(Seg("L", out_segs[-1].p1, end, segs[-1].z))
    return path


# ----------------------------------------------------------------------------------- interpreter
class Machine:
    def __init__(self, progs, params, offsets, work, tool_len, quirks=()):
        self.progs = progs
        self.quirks = set(quirks)     # wrong readings, used only by the dev misread battery
        self.dpi = 1 if "dpi1" in self.quirks else param_bit(params, 3401, 0)
        if param_bit(params, 5003, 0) != 0:
            raise NCError("only start-up type A modelled")
        self.off, self.work, self.tool_len = offsets, work, tool_len
        self.common = {}
        self.moves = []          # (kind, tool, p0, p1, arc) machine coords of tool tip
        self.reset()

    def reset(self):
        self.locals = [dict()]
        self.g90 = True
        self.motion = 0
        self.wcs = 1
        self.local_shift = (0.0, 0.0)
        self.rot = None                  # (cx, cy, deg)
        self.mirror = [None, None]       # mirror axis value for X, Y
        self.h = None                    # H number
        self.tool = None
        self.next_tool = None
        self.pos = None                  # program coords [x, y, z] in current frame
        self.mpos = None                 # machine tip coords
        self.comp = None                 # (side, d, start_point, segs)
        self.cycle = None
        self.retract_init = True

    # variables
    def getvar(self, n):
        if n == 0:
            return None
        if 1 <= n <= 33:
            return self.locals[-1].get(n)
        if 100 <= n <= 199 or 500 <= n <= 999:
            return self.common.get(n)
        for base, key in ((10000, "Hw"), (11000, "Hg"), (12000, "Dw"), (13000, "Dg")):
            if base < n <= base + 400:
                return self.off[key].get(n - base, 0.0)
        raise NCError(f"variable #{n} not supported")

    def setvar(self, n, v):
        if 1 <= n <= 33:
            self.locals[-1][n] = v
        elif 100 <= n <= 199 or 500 <= n <= 999:
            self.common[n] = v
        else:
            raise NCError(f"cannot write #{n}")

    def ev(self, s):
        e = Expr(self, tokenize(s))
        v = e.expr()
        if e.i != len(e.t):
            raise NCError(f"trailing tokens in {s}")
        return v

    def evcond(self, s):
        s = s.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        e = Expr(self, tokenize(s))
        v = e.cond()
        if e.i != len(e.t):
            raise NCError(f"trailing tokens in {s}")
        return v

    # frames
    def to_machine(self, p):
        x, y, z = p
        if self.mirror[0] is not None:
            x = 2 * self.mirror[0] - x
        if self.mirror[1] is not None:
            y = 2 * self.mirror[1] - y
        if self.rot is not None:
            cx, cy, a = self.rot
            v = rot((x - cx, y - cy), a)
            x, y = cx + v[0], cy + v[1]
        w, e = self.work[self.wcs], self.work[0]
        if "no_ext" in self.quirks:
            e = [0.0, 0.0, 0.0]
        hv = self.hval() if self.h else None
        if hv is None:
            raise NCError("Z move without tool length offset")
        L = self.tool_len[self.tool]
        return (x + self.local_shift[0] + w[0] + e[0],
                y + self.local_shift[1] + w[1] + e[1],
                z + w[2] + e[2] + hv - L)

    def hval(self):
        h = self.tool if "h_is_tool" in self.quirks else self.h
        hw = 0.0 if "no_hwear" in self.quirks else self.off["Hw"].get(h, 0.0)
        return self.off["Hg"].get(h, 0.0) + hw

    def from_machine(self, m):
        w, e = self.work[self.wcs], self.work[0]
        if "no_ext" in self.quirks:
            e = [0.0, 0.0, 0.0]
        hv = self.hval()
        L = self.tool_len[self.tool]
        x = m[0] - self.local_shift[0] - w[0] - e[0]
        y = m[1] - self.local_shift[1] - w[1] - e[1]
        z = m[2] - w[2] - e[2] - hv + L
        if self.rot is not None:
            cx, cy, a = self.rot
            v = rot((x - cx, y - cy), -a)
            x, y = cx + v[0], cy + v[1]
        if self.mirror[0] is not None:
            x = 2 * self.mirror[0] - x
        if self.mirror[1] is not None:
            y = 2 * self.mirror[1] - y
        return [x, y, z]

    def refresh(self):
        """frame changed: the tool stays put, its programmed position is re-expressed"""
        if self.mpos is not None and self.pos is not None and None not in self.pos:
            self.pos = self.from_machine(self.mpos)

    def mirrored_odd(self):
        return (self.mirror[0] is not None) != (self.mirror[1] is not None)

    def emit(self, kind, p_new, arc=None):
        m_new = self.to_machine(p_new)
        if self.mpos is not None:
            a = None
            if arc is not None:
                c, ccw = arc
                cm = self.to_machine((c[0], c[1], p_new[2]))
                flip = self.mirrored_odd() and "mirror_keeps_arcs" not in self.quirks
                a = ((cm[0], cm[1]), ccw != flip)
            self.moves.append((kind, self.tool, self.mpos, m_new, a))
        self.mpos = m_new
        self.pos = list(p_new)

    # word parsing
    def words(self, line):
        out = []
        i = 0
        while i < len(line):
            c = line[i]
            if c == " ":
                i += 1
                continue
            if not c.isalpha():
                raise NCError(f"bad block {line!r}")
            i += 1
            j = i
            if j < len(line) and line[j] in "-+":
                j += 1
            if j < len(line) and line[j] == "[":
                depth = 0
                while True:
                    if line[j] == "[":
                        depth += 1
                    elif line[j] == "]":
                        depth -= 1
                        if depth == 0:
                            j += 1
                            break
                    j += 1
                raw = line[i:j]
                out.append((c, raw, "expr"))
            elif j < len(line) and line[j] == "#":
                j += 1
                if line[j] == "[":
                    depth = 0
                    while True:
                        if line[j] == "[":
                            depth += 1
                        elif line[j] == "]":
                            depth -= 1
                            if depth == 0:
                                j += 1
                                break
                        j += 1
                else:
                    while j < len(line) and line[j].isdigit():
                        j += 1
                out.append((c, line[i:j], "expr"))
            else:
                while j < len(line) and (line[j].isdigit() or line[j] == "."):
                    j += 1
                out.append((c, line[i:j], "num"))
            i = j
        return out

    def value(self, addr, raw, kind):
        if kind == "expr":
            return self.ev(raw)
        v = float(raw)
        if addr in AXIS_SCALED and "." not in raw and self.dpi == 0:
            v *= 0.001
        return v

    # ------------------------------------------------------------------ run
    def run(self, prog):
        stack = []          # (prog, pc, is_g65)
        cur, pc = prog, 0
        loops = {}
        steps = 0
        while True:
            steps += 1
            if steps > 200000:
                raise NCError("runaway")
            lines = self.progs[cur]
            if pc >= len(lines):
                raise NCError(f"fell off O{cur}")
            line = lines[pc]
            pc += 1
            m = re.match(r"^N(\d+)\s*", line)
            if m:
                line = line[m.end():]
            if not line:
                continue
            # ---------------- macro statements
            if line.startswith("#"):
                lhs, rhs = line.split("=", 1)
                n = int(round(self.ev(lhs[1:]))) if lhs[1] == "[" else int(lhs[1:])
                self.setvar(n, self.ev(rhs))
                continue
            if line.startswith("IF"):
                m = re.match(r"IF\s*(\[.*\])\s*GOTO\s*(\d+)$", line)
                if m:
                    if self.evcond(m.group(1)):
                        pc = self.find_label(cur, int(m.group(2)))
                    continue
                m = re.match(r"IF\s*(\[.*\])\s*THEN\s*#(\d+)\s*=(.*)$", line)
                if m:
                    if self.evcond(m.group(1)):
                        self.setvar(int(m.group(2)), self.ev(m.group(3)))
                    continue
                raise NCError(f"bad IF {line}")
            if line.startswith("GOTO"):
                pc = self.find_label(cur, int(line[4:]))
                continue
            if line.startswith("WHILE"):
                m = re.match(r"WHILE\s*(\[.*\])\s*DO(\d)$", line)
                if not self.evcond(m.group(1)):
                    pc = self.find_end(cur, pc, m.group(2))
                continue
            m = re.match(r"^END(\d)$", line)
            if m:
                pc = self.find_while(cur, pc - 1, m.group(1))
                continue
            # ---------------- NC block
            ws = self.words(line)
            gs = [self.value(a, r, k) for a, r, k in ws if a == "G"]
            mcodes = [int(self.value(a, r, k)) for a, r, k in ws if a == "M"]
            vals = {}
            for a, r, k in ws:
                if a in "GMN":
                    continue
                v = self.value(a, r, k)
                if v is None and "vacant_is_zero" in self.quirks:
                    v = 0.0
                if v is None:
                    continue      # vacant variable: address omitted
                vals[a] = v
            if 65 in [int(g) for g in gs]:
                for a, r, k in ws:
                    if a not in "GP" and k == "num" and "." not in r:
                        raise NCError(f"G65 argument without decimal point: {line}")
                args = {}
                for a, v in vals.items():
                    if a == "P":
                        continue
                    args[ARG_MAP[a]] = v
                stack.append((cur, pc, True))
                self.locals.append(args)
                cur, pc = int(vals["P"]), 0
                continue
            if 98 in mcodes:
                own = "m98_new_level" in self.quirks
                stack.append((cur, pc, own))
                if own:
                    self.locals.append(dict(self.locals[-1]))
                cur, pc = int(vals["P"]), 0
                continue
            if 99 in mcodes:
                cur, pc, g65 = stack.pop()
                if g65:
                    self.locals.pop()
                if "m99_restores_g90" in self.quirks:
                    self.g90 = True
                continue
            if 30 in mcodes:
                if self.comp:
                    raise NCError("M30 in compensation")
                return
            self.block(gs, mcodes, vals, line)

    def find_label(self, prog, n):
        for i, l in enumerate(self.progs[prog]):
            if re.match(rf"^N0*{n}(?!\d)", l):
                return i
        raise NCError(f"N{n} not found in O{prog}")

    def find_end(self, prog, pc, k):
        for i in range(pc, len(self.progs[prog])):
            if re.match(rf"^(N\d+\s*)?END{k}$", self.progs[prog][i]):
                return i + 1
        raise NCError("END not found")

    def find_while(self, prog, pc, k):
        for i in range(pc, -1, -1):
            if re.search(rf"DO{k}$", self.progs[prog][i]):
                return i
        raise NCError("WHILE not found")

    # ------------------------------------------------------------------ one NC block
    def block(self, gs, mcodes, vals, line):
        gi = [round(g, 1) for g in gs]
        one_shot = None
        new_comp = None
        for g in gi:
            if g in (0, 1, 2, 3):
                self.motion = int(g)
                self.cycle = None if self.cycle is None else self.cycle
                if self.cycle is not None:
                    self.cycle = None
            elif g == 90:
                self.g90 = True
            elif g == 91:
                self.g90 = False
            elif g in (54, 55, 56, 57, 58, 59):
                self.wcs = int(g) - 53
            elif g in (17, 21, 94, 49, 69):
                if g == 49:
                    self.h = None
                if g == 69:
                    self.rot = None
                    self.refresh()
            elif g == 40:
                new_comp = 40
            elif g in (41, 42):
                new_comp = int(g)
            elif g == 43:
                self.h = int(vals["H"])
            elif g in (10, 28, 52, 68):
                one_shot = int(g)
            elif g == 51.1:
                one_shot = 51.1
            elif g == 50.1:
                one_shot = 50.1
            elif g == 80:
                self.cycle = None
                self.motion = 0 if self.motion >= 80 else self.motion
            elif g in (81, 82, 83, 73, 85):
                self.motion = int(g)
                self.cycle = {"init": None}
            elif g == 98:
                self.retract_init = True
            elif g == 99:
                self.retract_init = False
            else:
                raise NCError(f"G{g} not modelled ({line})")
        if "T" in vals:
            self.next_tool = int(vals["T"])
        if 6 in mcodes:
            self.tool = int(self.next_tool)
        if one_shot == 10:
            if "no_g10" in self.quirks:
                return
            p = int(vals["P"])
            if int(vals["L"]) != 2:
                raise NCError("G10 only L2")
            for k, a in enumerate("XYZ"):
                if a in vals:
                    self.work[p][k] = vals[a] if self.g90 else self.work[p][k] + vals[a]
            return
        if one_shot == 52:
            if not self.g90:
                raise NCError("G91 G52 not modelled")
            nx, ny = vals.get("X", self.local_shift[0]), vals.get("Y", self.local_shift[1])
            if "g52_adds" in self.quirks:
                nx, ny = self.local_shift[0] + nx, self.local_shift[1] + ny
            self.local_shift = (nx, ny)
            if "Z" in vals:
                raise NCError("G52 Z not modelled")
            self.refresh()
            return
        if one_shot == 68:
            if not self.g90:
                raise NCError("G68 in G91 not modelled")
            self.rot = None if "no_g68" in self.quirks else (vals["X"], vals["Y"], vals["R"])
            self.refresh()
            return
        if one_shot == 51.1:
            if "X" in vals:
                self.mirror[0] = vals["X"]
            if "Y" in vals:
                self.mirror[1] = vals["Y"]
            self.refresh()
            return
        if one_shot == 50.1:
            if "X" in vals:
                self.mirror[0] = None
            if "Y" in vals:
                self.mirror[1] = None
            self.refresh()
            return
        if one_shot == 28:
            if self.g90 or set(vals) - {"Z"} or vals.get("Z") != 0:
                raise NCError("only G91 G28 Z0 modelled")
            if self.mpos is not None:
                top = (self.mpos[0], self.mpos[1], 0.0 - self.tool_len[self.tool])
                self.moves.append(("rapid", self.tool, self.mpos, top, None))
            self.mpos = None
            self.pos = None
            return
        if self.motion >= 80 and self.cycle is not None:
            self.do_cycle(vals)
            return
        axes = [a for a in "XYZ" if a in vals]
        if not axes and self.motion not in (2, 3) and new_comp is None:
            return
        if not axes and self.motion in (2, 3) and not ("I" in vals or "J" in vals or "R" in vals):
            return
        if self.pos is None:
            # first positioning after a tool change: needs absolute X Y then Z with G43
            if not self.g90:
                raise NCError("incremental move from unknown position")
            self.pos = [vals.get("X"), vals.get("Y"), vals.get("Z")]
            if self.pos[2] is None:
                return
            if None in self.pos:
                raise NCError("unknown position")
            self.mpos = self.to_machine(self.pos)
            return
        if None in self.pos:
            if "Z" in vals and self.g90:
                self.pos[2] = vals["Z"]
                if "X" in vals:
                    self.pos[0] = vals["X"]
                if "Y" in vals:
                    self.pos[1] = vals["Y"]
                if None in self.pos:
                    raise NCError("unknown position")
                self.mpos = self.to_machine(self.pos)
                return
            raise NCError("unknown position")
        tgt = list(self.pos)
        for k, a in enumerate("XYZ"):
            if a in vals:
                tgt[k] = vals[a] if self.g90 else self.pos[k] + vals[a]
        kind = "rapid" if self.motion == 0 else "feed"
        arc = None
        if self.motion in (2, 3):
            ccw = self.motion == 3
            if "R" in vals:
                c = arc_center(self.pos, tgt, vals["R"], ccw)
            else:
                c = (self.pos[0] + vals.get("I", 0.0), self.pos[1] + vals.get("J", 0.0))
            if abs(tgt[2] - self.pos[2]) > 1e-9:
                raise NCError("helical not modelled")
            arc = (c, ccw)
        # cutter compensation
        if new_comp in (41, 42):
            if self.motion not in (0, 1) or abs(tgt[2] - self.pos[2]) > 1e-9:
                raise NCError("start-up must be a linear XY move")
            dn = int(vals["D"])
            d = self.off["Dg"].get(dn, 0.0) + (0.0 if "no_dwear" in self.quirks else self.off["Dw"].get(dn, 0.0))
            self.comp = {"side": 1 if new_comp == 41 else -1, "d": d, "start": tuple(self.pos),
                         "segs": [Seg("L", tuple(self.pos[:2]), tuple(tgt[:2]), tgt[2])], "kind": kind}
            self.pos = tgt
            return
        if self.comp is not None and new_comp != 40:
            if abs(tgt[2] - self.pos[2]) > 1e-9:
                raise NCError("Z move inside compensation")
            if arc is None:
                s = Seg("L", tuple(self.pos[:2]), tuple(tgt[:2]), tgt[2])
            else:
                s = Seg("A", tuple(self.pos[:2]), tuple(tgt[:2]), tgt[2], arc[0], arc[1])
            self.comp["segs"].append(s)
            self.pos = tgt
            return
        if new_comp == 40 and self.comp is not None:
            if arc is not None or abs(tgt[2] - self.pos[2]) > 1e-9:
                raise NCError("cancel must be linear XY")
            c = self.comp
            segs = c["segs"]
            startup = segs[0]
            body = segs[1:]
            path = comp_path(startup.p0, body, tuple(tgt[:2]), c["d"], c["side"])
            z = tgt[2]
            p = list(self.pos)
            # the tool is still at the start-up point (uncompensated) in machine terms
            self.pos = [startup.p0[0], startup.p0[1], z]
            self.mpos = self.to_machine(self.pos)
            for s in path:
                if math.hypot(s.p1[0] - s.p0[0], s.p1[1] - s.p0[1]) < 1e-9 and s.kind == "L":
                    continue
                self.emit("feed", [s.p1[0], s.p1[1], z], None if s.kind == "L" else (s.c, s.ccw))
            self.comp = None
            self.pos = tgt
            return
        self.emit(kind, tgt, arc)

    def do_cycle(self, vals):
        c = self.cycle
        for a in "RZQF":
            if a in vals:
                c[a] = vals[a]
        if "X" not in vals and "Y" not in vals and "K" not in vals and c.get("done"):
            return
        if c["init"] is None:
            c["init"] = self.pos[2]
        reps = int(vals.get("K", 1))
        for _ in range(reps):
            tgt = list(self.pos)
            for k, a in enumerate("XY"):
                if a in vals:
                    tgt[k] = vals[a] if self.g90 else self.pos[k] + vals[a]
            if self.g90:
                rz, bz = c["R"], c["Z"]
            elif "g91_z_from_init" in self.quirks:
                rz = c["init"] + c["R"]
                bz = c["init"] + c["Z"]
            else:
                rz = c["init"] + c["R"]
                bz = rz + c["Z"]
            self.emit("rapid", [tgt[0], tgt[1], self.pos[2]])
            self.emit("rapid", [tgt[0], tgt[1], rz])
            self.emit("feed", [tgt[0], tgt[1], bz])
            self.emit("rapid", [tgt[0], tgt[1], c["init"] if self.retract_init else rz])
            c["done"] = True


def run_part(cncdir, progs_to_run, tool_len, quirks=()):
    """run each program in order on a fresh control state (program state resets at M30,
    the offset memory does not). returns the list of move lists, one per program"""
    if isinstance(cncdir, dict):          # an in-memory control state (see history.load_state)
        progs, params = cncdir["progs"], cncdir["params"]
        off = cncdir["off"]
        work = {k: list(v) for k, v in cncdir["work"].items()}
    else:
        progs = load_programs(f"{cncdir}/ALL-PROG.TXT")
        params = read_params(f"{cncdir}/CNC-PARA.TXT")
        off = read_offsets(f"{cncdir}/TOOLOFST.TXT")
        work = read_work(f"{cncdir}/EXT_WKZ.TXT")
    out = []
    for o in progs_to_run:
        m = Machine(progs, params, off, work, tool_len, quirks)
        m.run(o)
        out.append(m.moves)
        work = m.work
    return out
