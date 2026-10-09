"""Random copybook AST generation, per-record value assignment, and expected JSON.

The AST is independent of the decoder's parser: the generator emits copybook text from it
and the decoder has to parse that text back. Only the picture model (picture.py) and the
elementary byte-fill semantics (decode_elementary on a constant byte fill) are shared.
"""

import random
import struct
import sys

sys.path.insert(0, "/sol")
from unpack.picture import Picture          # noqa: E402
from unpack.layout import binary_size       # noqa: E402
from unpack.decode import decode_elementary, canon  # noqa: E402

from names import PREFIXES, WORDS, STRINGS  # noqa: E402


class G:
    """Generator-side item."""
    _ids = 0

    def __init__(self, name, pic=None, usage=None):
        G._ids += 1
        self.id = G._ids
        self.name = name
        self.pic_text = pic
        self.pic = Picture(pic) if pic else None
        self.usage = usage            # explicit usage word as written, or None
        self.sign = None              # ("LEADING"|"TRAILING", sep)
        self.sync = False
        self.just = False
        self.bwz = False
        self.occurs = None            # {"min","max","dep": G or None, "indexed": bool, "key": bool}
        self.redefines = None         # G
        self.redefined_by = []
        self.children = []
        self.parent = None
        self.value = None             # cosmetic VALUE clause text (list of literal strings)
        self.conds = []               # [(name, [values...], thru_pairs)]
        self.copy = None              # ("FILE.cpy", tag, prefix, literal_form)
        self.eff_usage = "DISPLAY"
        self.eff_sign = None
        self.unset_p = 0.0
        self.is_disc = False
        self.is_count = False

    @property
    def is_group(self):
        return bool(self.children)

    @property
    def filler(self):
        return self.name == "FILLER"

    def add(self, c):
        c.parent = self
        self.children.append(c)
        return c

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def in_occurs(self):
        p = self.parent
        while p is not None:
            if p.occurs:
                return True
            p = p.parent
        return False


def inherit(it, usage="DISPLAY", sign=None):
    u = {"COMP": "COMP", "COMPUTATIONAL": "COMP", "BINARY": "COMP", "COMP-4": "COMP",
         "COMPUTATIONAL-4": "COMP", "COMP-5": "COMP-5", "COMPUTATIONAL-5": "COMP-5",
         "COMP-3": "COMP-3", "COMPUTATIONAL-3": "COMP-3", "PACKED-DECIMAL": "COMP-3",
         "COMP-6": "COMP-6", "COMPUTATIONAL-6": "COMP-6", "COMP-1": "COMP-1",
         "COMPUTATIONAL-1": "COMP-1", "COMP-2": "COMP-2", "COMPUTATIONAL-2": "COMP-2",
         "DISPLAY": "DISPLAY"}
    it.eff_usage = u[it.usage] if it.usage else usage
    it.eff_sign = it.sign or sign
    for c in it.children:
        inherit(c, it.eff_usage, it.eff_sign)


def elem_bytes(it):
    u = it.eff_usage
    if u == "COMP-1":
        return 4
    if u == "COMP-2":
        return 8
    p = it.pic
    if u == "DISPLAY":
        if p.category == "numeric":
            return p.digits + (1 if (p.signed and it.eff_sign and it.eff_sign[1]) else 0)
        return p.size
    if u in ("COMP", "COMP-5"):
        return binary_size(p.digits)
    if u == "COMP-3":
        return (p.digits + 2) // 2
    if u == "COMP-6":
        return (p.digits + 1) // 2
    raise ValueError(u)


def approx_size(it):
    """Size ignoring SYNC padding (the generator never puts SYNC under a REDEFINES)."""
    if it.children:
        s = 0
        for c in it.children:
            if c.redefines:
                continue
            s += approx_size(c)
    else:
        s = elem_bytes(it)
    if it.occurs:
        s *= it.occurs["max"]
    return s


# --------------------------------------------------------------------------- pictures

ALNUM_PICS = ["X(%d)", "X(%d)", "X(%d)", "XXX", "XX", "X", "A(%d)", "X(%d)"]
EDITED_NUM = [
    ("ZZ,ZZ9.99-", 1), ("Z(4)9.99", 1), ("$$$,$$9.99", 1), ("+9(3)", 1), ("-(5)9", 1),
    ("9(6).99CR", 1), ("9(4)/99/99", 1), ("***,**9.99", 1), ("ZZZ9", 2), ("+ZZ9.9", 1),
    ("Z(3)9-", 1), ("999B999", 1), ("$$9.99", 1), ("9(6).99DB", 1), ("ZZ9", 1),
    ("-ZZ,ZZ9", 1), ("Z(5)9", 1), ("9(3).9(3)", 1), ("+(4)9.99", 1),
    ("$(5)9.99CR", 1), ("*(4)9", 1), ("Z,ZZZ,ZZ9", 1), ("99.99", 1), ("-999", 1),
]
EDITED_ALNUM = ["XXBXX", "XXXX/XX", "XXBXXBXX", "X(3)/X(3)", "XX0XX", "XXXBX(4)"]


def rnd_alnum_pic(rng, small=False):
    p = rng.choice(ALNUM_PICS)
    if "%d" in p:
        n = rng.choice([1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 60]) if not small else rng.choice([1, 2, 3, 4])
        p = p % n
    return p


def rnd_numeric_pic(rng, usage):
    if usage in ("COMP", "COMP-5"):
        d = rng.choice([1, 2, 3, 4, 4, 5, 6, 7, 8, 9, 9, 10, 12, 15, 18])
    elif usage == "COMP-6":
        d = rng.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13])
    else:
        d = rng.choice([1, 2, 3, 4, 5, 5, 6, 7, 7, 8, 9, 10, 11, 13, 15, 18])
    signed = rng.random() < (0.6 if usage != "COMP-6" else 0.0)
    scale = 0
    if rng.random() < 0.45 and d >= 2:
        scale = rng.choice([1, 2, 2, 2, 3, 4, 5])
        scale = min(scale, d - 1) if rng.random() < 0.9 else min(scale, d)
    form = rng.random()
    if scale == 0:
        if form < 0.5:
            body = "9(%d)" % d
        elif form < 0.8 or d > 6:
            body = "9(%d)" % d if d > 8 else "9" * d
        else:
            body = "9" * d
    else:
        i = d - scale
        if form < 0.5:
            body = ("9(%d)V9(%d)" % (i, scale)) if i else ("V9(%d)" % scale)
        elif form < 0.8:
            body = ("9(%d)V%s" % (i, "9" * scale)) if i else ("V" + "9" * scale)
        else:
            body = ("%sV%s" % ("9" * i, "9" * scale)) if i else ("V" + "9" * scale)
    # P scaling, DISPLAY / COMP-3 only
    if usage in ("DISPLAY", "COMP-3") and scale == 0 and rng.random() < 0.08 and d <= 6:
        if rng.random() < 0.5:
            body = "9(%d)%s" % (d, "P" * rng.choice([1, 2, 3]))
        else:
            body = "%s%s" % ("V" if rng.random() < 0.6 else "", "P" * rng.choice([1, 2]) + "9(%d)" % d)
    return ("S" if signed else "") + body


# --------------------------------------------------------------------------- names

class Namer:
    def __init__(self, rng):
        self.rng = rng
        self.used = set()

    def name(self, prefix=None, k=None):
        rng = self.rng
        for _ in range(200):
            pre = prefix or rng.choice(PREFIXES)
            n = k or rng.choice([1, 2, 2, 3])
            parts = [pre] + [rng.choice(WORDS) for _ in range(n)]
            if rng.random() < 0.15:
                parts.append(str(rng.randint(1, 9)))
            nm = "-".join(parts)
            if len(nm) <= 30 and nm not in self.used and nm != "FILLER":
                self.used.add(nm)
                return nm
        raise RuntimeError("name space exhausted")


# --------------------------------------------------------------------------- builder

class Ctx:
    def __init__(self, rng, opts):
        self.rng = rng
        self.opts = opts
        self.namer = Namer(rng)
        self.prefix = rng.choice(PREFIXES)
        self.features = set()
        self.copies = []          # list of G groups that are COPY'd
        self.discs = []           # discriminator items
        self.variants = []        # (orig G, disc G, map, default)
        self.odo = None

    def f(self, name):
        self.features.add(name)


def usage_menu(ctx):
    rng = ctx.rng
    if ctx.opts["line_seq"]:
        return "DISPLAY"
    r = rng.random()
    if r < 0.40:
        return "DISPLAY"
    if r < 0.58:
        return "COMP-3"
    if r < 0.72:
        return "COMP"
    if r < 0.80:
        return "COMP-5"
    if r < 0.86:
        return "COMP-6"
    if r < 0.92:
        return "COMP-1"
    return "COMP-2"


def usage_word(ctx, u):
    rng = ctx.rng
    table = {
        "DISPLAY": [None, None, None, "DISPLAY"],
        "COMP": ["COMP", "COMP", "BINARY", "COMPUTATIONAL", "COMP-4", "COMPUTATIONAL-4"],
        "COMP-5": ["COMP-5", "COMP-5", "COMPUTATIONAL-5"],
        "COMP-3": ["COMP-3", "COMP-3", "COMP-3", "PACKED-DECIMAL", "COMPUTATIONAL-3"],
        "COMP-6": ["COMP-6", "COMPUTATIONAL-6"],
        "COMP-1": ["COMP-1", "COMPUTATIONAL-1"],
        "COMP-2": ["COMP-2", "COMPUTATIONAL-2"],
    }
    return rng.choice(table[u])


def make_elem(ctx, inherited_usage=None, inherited_sign=None, allow_sync=True, small=False):
    rng = ctx.rng
    r = rng.random()
    it = None
    if r < 0.42:
        pic = rnd_alnum_pic(ctx.rng, small)
        it = G(ctx.namer.name(ctx.prefix), pic)
        if rng.random() < 0.08 and not it.pic.category == "numeric":
            it.just = True
            ctx.f("just")
    elif r < 0.50 and not small:
        pic, _ = rng.choice(EDITED_NUM)
        it = G(ctx.namer.name(ctx.prefix), pic)
        ctx.f("num-edited")
        if rng.random() < 0.25 and "*" not in pic:
            it.bwz = True
            ctx.f("bwz")
    elif r < 0.53 and not small:
        pic = rng.choice(EDITED_ALNUM)
        it = G(ctx.namer.name(ctx.prefix), pic)
        ctx.f("alnum-edited")
    else:
        u = inherited_usage or usage_menu(ctx)
        if u in ("COMP-1", "COMP-2"):
            it = G(ctx.namer.name(ctx.prefix), None)
            ctx.f(u.lower())
        else:
            pic = rnd_numeric_pic(rng, u)
            it = G(ctx.namer.name(ctx.prefix), pic)
            if "P" in pic:
                ctx.f("p-scale")
            if u != "DISPLAY":
                ctx.f(u.lower())
        it.eff_usage = u
        if inherited_usage is None and u != "DISPLAY":
            it.usage = usage_word(ctx, u)
        elif inherited_usage is None and rng.random() < 0.1:
            it.usage = "DISPLAY"
        if u == "DISPLAY" and it.pic is not None and it.pic.signed and inherited_sign is None and rng.random() < 0.3:
            it.sign = (rng.choice(["LEADING", "TRAILING"]), rng.random() < 0.6)
            ctx.f("sign-%s%s" % (it.sign[0].lower(), "-sep" if it.sign[1] else ""))
        it.eff_sign = it.sign or inherited_sign
        if u == "DISPLAY" and it.pic is not None and not it.pic.signed and it.pic.scale == 0 and "P" not in it.pic_text and rng.random() < 0.06:
            it.bwz = True
            ctx.f("bwz-display")
        if u in ("COMP", "COMP-5", "COMP-1", "COMP-2") and allow_sync and rng.random() < 0.35:
            it.sync = True
            ctx.f("sync")
    if rng.random() < 0.12 and it.pic is not None:
        it.value = _value_clause(ctx, it)
    if rng.random() < 0.10 and it.pic is not None:
        it.conds = _conds(ctx, it)
    return it


def _value_clause(ctx, it):
    rng = ctx.rng
    ctx.f("value")
    p = it.pic
    if p.category in ("alnum", "alnum_edited"):
        r = rng.random()
        if r < 0.3:
            return ["SPACES"]
        if r < 0.45:
            ctx.f("value-period")
            return ["'" + rng.choice([".", "N.A.", "A.B", "X. Y.", "END."]) + "'"]
        if r < 0.55:
            ctx.f("value-quote")
            return ['"' + rng.choice(["O'NEIL", "IT'S", "'"]) + '"']
        if r < 0.7 and p.size >= 30:
            ctx.f("continuation")
            return ["LONGLIT"]
        return ["'" + rng.choice(["Y", "N", "ABC", "  ", "00", "?"])[:p.size] + "'"]
    if p.category == "numeric":
        return [rng.choice(["ZERO", "ZEROS", "ZEROES", "0", "1", "99"])]
    return None


def _conds(ctx, it):
    rng = ctx.rng
    ctx.f("88")
    p = it.pic
    out = []
    for _ in range(rng.randint(1, 3)):
        nm = ctx.namer.name(ctx.prefix, 1)
        if p.category in ("alnum", "alnum_edited"):
            vals = ["'%s'" % rng.choice(["A", "B", "C", "X", "Y", "Z", "01", "99", ".", " "])[:p.size]
                    for _ in range(rng.randint(1, 3))]
            if rng.random() < 0.3 and p.size == 1:
                vals = ["'A' THRU 'F'"]
                ctx.f("88-thru")
        else:
            vals = [str(rng.randint(0, 9)) for _ in range(rng.randint(1, 2))]
            if rng.random() < 0.3:
                vals = ["1 THRU 5"]
                ctx.f("88-thru")
        out.append((nm, vals))
    return out


def make_group(ctx, depth, budget, allow_sync=True, in_occurs=False, allow_special=True,
               inherited_usage=None, inherited_sign=None):
    rng = ctx.rng
    g = G(ctx.namer.name(ctx.prefix))
    if inherited_usage is None and inherited_sign is None:
        if rng.random() < 0.12 and not ctx.opts["line_seq"]:
            u = rng.choice(["COMP-3", "COMP", "COMP-3", "COMP-5"])
            g.usage = usage_word(ctx, u)
            inherited_usage = u
            ctx.f("group-usage")
        elif rng.random() < 0.08:
            g.sign = (rng.choice(["LEADING", "TRAILING"]), rng.random() < 0.7)
            inherited_sign = g.sign
            ctx.f("group-sign")
    n = rng.randint(2, 6)
    for _ in range(n):
        r = rng.random()
        if depth < 3 and r < 0.18 and budget > 4:
            c = make_group(ctx, depth + 1, budget - 2, allow_sync, in_occurs, allow_special,
                           inherited_usage, inherited_sign)
            budget -= 2
        elif depth < 3 and r < 0.30 and allow_special and budget > 4 and inherited_usage is None and inherited_sign is None:
            c = make_table(ctx, depth + 1, allow_sync, nested=in_occurs)
            budget -= 3
        else:
            if inherited_usage:
                c = make_numeric_under(ctx, inherited_usage, inherited_sign)
            elif inherited_sign:
                if rng.random() < 0.7:
                    c = make_numeric_under(ctx, "DISPLAY", inherited_sign)
                else:
                    c = G(ctx.namer.name(ctx.prefix), rnd_alnum_pic(rng))
                    c.eff_sign = inherited_sign
            else:
                c = make_elem(ctx, None, None, allow_sync)
        g.add(c)
    if inherited_usage is None and rng.random() < 0.25:
        f = G("FILLER", rnd_alnum_pic(rng, True))
        g.add(f)
        ctx.f("filler")
    return g


def make_numeric_under(ctx, u, sign):
    rng = ctx.rng
    pic = rnd_numeric_pic(rng, u)
    it = G(ctx.namer.name(ctx.prefix), pic)
    it.eff_usage = u
    it.eff_sign = sign
    if "P" in pic:
        ctx.f("p-scale")
    if u == "DISPLAY" and it.pic.signed and sign is None and rng.random() < 0.3:
        it.sign = (rng.choice(["LEADING", "TRAILING"]), rng.random() < 0.6)
    return it


def make_table(ctx, depth, allow_sync, nested=False):
    rng = ctx.rng
    ctx.f("occurs")
    if rng.random() < 0.3:
        # elementary table
        it = make_elem(ctx, None, None, allow_sync)
        it.occurs = {"min": 0, "max": rng.choice([2, 3, 4, 5, 6, 8, 10, 12]), "dep": None,
                     "indexed": rng.random() < 0.3, "key": False}
        it.occurs["min"] = it.occurs["max"]
        it.conds = []
        return it
    # no SYNC inside an inner (nested) table: cobc 3.2 shifts the last child of a padded
    # element, which makes synchronized items in nested tables overlap the next element
    g = make_group(ctx, depth, 5, allow_sync and not nested, in_occurs=True, allow_special=(depth < 2 and not nested))
    if any(c.sync for c in g.walk()):
        # an inner table must not carry SYNC either, and the element's last child must be a
        # plain elementary item so the padding shift stays inside the element
        for c in g.walk():
            if c is not g and c.occurs:
                for x in c.walk():
                    x.sync = False
        last = g.children[-1]
        if last.children or last.occurs:
            g.add(make_elem(ctx, None, None, allow_sync=False, small=True))
    g.occurs = {"min": 0, "max": rng.choice([2, 3, 3, 4, 5, 6, 8, 10]), "dep": None,
                "indexed": rng.random() < 0.35, "key": rng.random() < 0.15}
    g.occurs["min"] = g.occurs["max"]
    if g.occurs["indexed"]:
        ctx.f("indexed")
    if g.occurs["key"]:
        ctx.f("occurs-key")
    if any(c.sync for c in g.walk()):
        ctx.f("sync-occurs")
    if any(c.occurs for c in g.children):
        ctx.f("nested-occurs")
    return g


def make_disc(ctx, keys_kind):
    """Discriminator field: X(1)/X(2) or 9(1)/9(2)."""
    rng = ctx.rng
    if keys_kind == "alnum":
        pic = rng.choice(["X", "X", "X(2)", "XX"])
    else:
        pic = rng.choice(["9", "9(2)", "99"])
    d = G(ctx.namer.name(ctx.prefix), pic)
    d.is_disc = True
    if rng.random() < 0.5:
        d.conds = _conds(ctx, d)
    return d


def disc_keys(ctx, d, n):
    rng = ctx.rng
    p = d.pic
    pool = []
    if p.category == "alnum":
        letters = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
        while len(pool) < n:
            k = "".join(rng.choice(letters) for _ in range(p.size))
            if rng.random() < 0.3 and p.size == 2:
                k = k[0]   # short key, stored with a trailing space, decoded trimmed
            if k not in pool:
                pool.append(k)
    else:
        vals = list(range(0, 10 ** p.digits))
        rng.shuffle(vals)
        pool = [canon(v, 0) for v in vals[:n]]
    return pool


def make_redefines_set(ctx, depth):
    rng = ctx.rng
    ctx.f("redefines")
    orig = make_group(ctx, depth + 1, 5, allow_sync=False, allow_special=False)
    inherit(orig)
    osz = approx_size(orig)
    alts = [orig]
    for _ in range(rng.randint(1, 2)):
        for _try in range(30):
            alt = make_group(ctx, depth + 1, 4, allow_sync=False, allow_special=False)
            inherit(alt)
            sz = approx_size(alt)
            if sz <= osz:
                break
            # drop children until it fits
            while alt.children and approx_size(alt) > osz:
                alt.children.pop()
            if alt.children and approx_size(alt) <= osz:
                break
        else:
            continue
        if not alt.children:
            continue
        if approx_size(alt) < osz and rng.random() < 0.5 and alt.usage is None:
            pad = osz - approx_size(alt)
            if pad <= 200:
                alt.add(G("FILLER", "X(%d)" % pad if pad > 1 else "X"))
        alt.redefines = orig
        orig.redefined_by.append(alt)
        alts.append(alt)
    return alts


def build_layout(ctx, first_disc=None):
    """One 01 record. Returns G root."""
    rng = ctx.rng
    if rng.random() < 0.5:
        rname = ctx.namer.name(ctx.prefix, 1)
    else:
        for _ in range(50):
            rname = ctx.prefix + "-" + rng.choice(["REC", "RECORD", "MASTER", "DETAIL", "HDR", "TRL", "ROW", "LINE", "AREA"])
            if rname not in ctx.namer.used:
                break
        ctx.namer.used.add(rname)
    root = G(rname)
    if first_disc is not None:
        root.add(first_disc)
    n = rng.randint(4, 12)
    budget = 20
    pending_redef = []
    for i in range(n):
        r = rng.random()
        if r < 0.22 and budget > 5:
            root.add(make_group(ctx, 1, 6))
            budget -= 2
        elif r < 0.34 and budget > 5:
            root.add(make_table(ctx, 1, True))
            budget -= 3
        elif r < 0.44 and budget > 5 and not ctx.opts["line_seq"] or (r < 0.40 and ctx.opts["line_seq"] and budget > 5):
            alts = make_redefines_set(ctx, 1)
            if len(alts) > 1 and rng.random() < 0.7:
                disc = make_disc(ctx, "alnum" if rng.random() < 0.75 else "num")
                root.add(disc)
                keys = disc_keys(ctx, disc, len(alts) + 1)
                mp = {}
                for k, a in zip(keys, alts):
                    mp[k] = a
                default = None
                rr = rng.random()
                if rr < 0.5:
                    default = alts[0]
                elif rr < 0.7:
                    default = rng.choice(alts)
                ctx.variants.append((alts[0], disc, mp, default, keys[len(alts)]))
                ctx.f("variants")
            else:
                ctx.f("redef-base")
            for a in alts:
                root.add(a)
            budget -= 3
        elif r < 0.52 and ctx.opts["copy"] and not any(c.copy for c in root.walk()):
            g = make_group(ctx, 1, 5, allow_sync=False, allow_special=False)
            tag = rng.choice(["PFX", "TAG", "PRE", "ID", "P", "NM"])
            g.copy = (rng.choice(["ADDR", "AMTS", "KEYS", "AUDIT", "DATES", "PARTY"]) +
                      rng.choice(["", "REC", "BLK", "GRP"]), tag, rng.random() < 0.5)
            root.add(g)
            ctx.f("copy-replacing")
            budget -= 2
        else:
            root.add(make_elem(ctx))
    # ODO: last item, only for the (single) main layout
    if ctx.opts["odo"] and ctx.odo is None:
        t = make_table(ctx, 1, True)
        mx = t.occurs["max"]
        mn = rng.choice([0, 0, 1, 1, 2])
        if mx < 3:
            mx = 3
        t.occurs["max"] = mx
        t.occurs["min"] = min(mn, mx - 1)
        # the count item must be able to hold the maximum occurrence number
        pics = ["9(2)", "99", "S9(4)", "9(3)"] + (["9"] if mx <= 9 else [])
        cnt = G(ctx.namer.name(ctx.prefix, 1), rng.choice(pics))
        u = rng.choice(["DISPLAY", "DISPLAY", "COMP", "COMP-3"])
        if u != "DISPLAY" and not ctx.opts["line_seq"]:
            cnt.usage = usage_word(ctx, u)
            cnt.eff_usage = u
        cnt.is_count = True
        root.add(cnt)
        t.occurs["dep"] = cnt
        ctx.odo = t
        ctx.f("odo")
        root.add(t)
    if rng.random() < 0.15:
        ctx.f("renames")
        root.renames = True   # emitter picks two consecutive elementary siblings
    # remove SYNC under non-OCCURS where line seq (already excluded by usage menu)
    return root


def build_case(seed, opts):
    rng = random.Random(seed)
    ctx = Ctx(rng, opts)
    layouts = []
    if opts["multi01"]:
        n = rng.choice([2, 2, 3])
        kind = "alnum" if rng.random() < 0.8 else "num"
        discs = [make_disc(ctx, kind) for _ in range(n)]
        # same picture for every layout's leading type field
        for d in discs[1:]:
            d.pic_text = discs[0].pic_text
            d.pic = Picture(d.pic_text)
        for d in discs:
            d.conds = []
        keys = disc_keys(ctx, discs[0], n + 1)
        for d in discs:
            layouts.append(build_layout(ctx, d))
        mp = {k: L for k, L in zip(keys, layouts)}
        default = None
        rr = rng.random()
        if rr < 0.5:
            default = layouts[0]
        elif rr < 0.65:
            default = rng.choice(layouts)
        ctx.layouts = (discs[0], mp, default, keys[n])
        ctx.f("multi01")
    else:
        layouts.append(build_layout(ctx))
        ctx.layouts = None
    for L in layouts:
        inherit(L)
    ctx.records = layouts
    # unset probabilities: a few numeric/alnum fields per case
    elems = [it for L in layouts for it in L.walk() if not it.children and not it.filler
             and not it.is_disc and not it.is_count]
    for it in rng.sample(elems, min(len(elems), rng.randint(1, 4))):
        it.unset_p = rng.choice([0.1, 0.2, 0.4])
        ctx.f("unset")
    return ctx


# --------------------------------------------------------------------------- values

def _rand_string(rng, n, alpha_only=False):
    r = rng.random()
    if r < 0.6:
        s = rng.choice(STRINGS)
    elif r < 0.75:
        s = " ".join(rng.choice(STRINGS) for _ in range(2))
    elif r < 0.85:
        s = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(rng.randint(1, max(1, n))))
    elif r < 0.92:
        s = "".join(chr(rng.randint(0x21, 0x7E)) for _ in range(rng.randint(1, max(1, n))))
    else:
        s = ""
    if alpha_only:
        s = "".join(c for c in s if c.isalpha() or c == " ").upper()
    s = s.replace('"', "'")
    s = s[:n]
    return s


def gen_value(ctx, it):
    """-> (cobol literal text, expected json value)"""
    rng = ctx.rng
    u = it.eff_usage
    p = it.pic
    if u == "COMP-1":
        k = rng.randint(0, 10)
        m = rng.randint(-(2 ** 20) + 1, 2 ** 20 - 1)
        v = m / (2 ** k)
        return _dec_literal(m, k), float(struct.unpack("<f", struct.pack("<f", v))[0])
    if u == "COMP-2":
        k = rng.randint(0, 8)
        m = rng.randint(-(2 ** 30) + 1, 2 ** 30 - 1)
        v = m / (2 ** k)
        return _dec_literal(m, k), float(v)
    cat = p.category
    if cat == "alnum":
        n = min(p.size, 50)
        s = _rand_string(rng, n, alpha_only=(set(it.pic_text.replace("(", "").replace(")", "")) <= set("A0123456789")))
        if it.just:
            exp = (" " * (p.size - len(s)) + s).lstrip(" ")
        else:
            exp = s.rstrip(" ")
        return '"%s"' % s, exp
    if cat == "alnum_edited":
        nx = sum(1 for c in p.symbols if c in "XA9")
        s = _rand_string(rng, nx)
        src = list(s.ljust(nx))
        out = []
        for c in p.symbols:
            if c in "XA9":
                out.append(src.pop(0))
            elif c == "B":
                out.append(" ")
            elif c == "0":
                out.append("0")
            elif c == "/":
                out.append("/")
        return '"%s"' % s, "".join(out).rstrip(" ")
    if cat == "numeric":
        d = _rand_digits(rng, p.digits)
        if p.signed and rng.random() < 0.45:
            d = -d
        if u in ("COMP", "COMP-5") and not p.signed:
            d = abs(d)
        return _num_literal(d, p.scale), canon(d, p.scale)
    # numeric edited
    d = _rand_digits(rng, p.digits)
    if p.signed and rng.random() < 0.45:
        d = -d
    if it.bwz and rng.random() < 0.3:
        d = 0
    return _num_literal(d, p.scale), canon(d, p.scale)


def _rand_digits(rng, digits):
    r = rng.random()
    hi = 10 ** digits - 1
    if r < 0.1:
        return 0
    if r < 0.15:
        return hi
    if r < 0.45:
        return rng.randint(0, min(hi, 999))
    return rng.randint(0, hi)


def _num_literal(unscaled, scale):
    if scale <= 0:
        return str(unscaled * 10 ** (-scale))
    neg = unscaled < 0
    a = abs(unscaled)
    ip, fp = divmod(a, 10 ** scale)
    return ("-" if neg else "") + "%d.%0*d" % (ip, scale, fp)


def _dec_literal(m, k):
    """m / 2**k as an exact decimal literal."""
    neg = m < 0
    a = abs(m)
    scale = k          # m/2^k = m*5^k / 10^k
    unscaled = a * (5 ** k)
    ip, fp = divmod(unscaled, 10 ** scale)
    s = "%d" % ip if scale == 0 else "%d.%0*d" % (ip, scale, fp)
    return ("-" if neg else "") + s


FILLS = {"space": b" ", "low": b"\x00", "high": b"\xff"}


class _View:
    def __init__(self, it):
        self.__dict__["_it"] = it

    def __getattr__(self, k):
        if k == "offset":
            return 0
        if k == "elem_size":
            return elem_bytes(self._it)
        return getattr(self._it, k)


def fill_expected(it, fill):
    n = elem_bytes(it)
    return decode_elementary(FILLS[fill] * n, 0, _View(it))


def assign_record(ctx, rec_index):
    """Choose a layout, variants, ODO count and every elementary value for one record.
    Returns dict with keys: layout (G), init ('space'|'low'), entries {(id, subs): entry},
    chosen_variants {orig id: chosen G or None}, count int|None."""
    rng = ctx.rng
    init = ctx.opts["init"]
    r = {"init": init, "entries": {}, "variants": {}, "count": None}
    # layout
    if ctx.layouts:
        disc, mp, default, offkey = ctx.layouts
        keys = list(mp.keys())
        if default is not None and rng.random() < 0.15:
            key = offkey
            L = default
        else:
            key = rng.choice(keys)
            L = mp[key]
        r["layout"] = L
        r["disc_key"] = key
        # the layout's own leading type field carries the key
        own = L.children[0]
        r["entries"][(own.id, ())] = {"kind": "move", "lit": _disc_lit(own, key), "json": _disc_json(own, key)}
    else:
        L = ctx.records[0]
        r["layout"] = L
    # variants (only those inside L)
    for orig, disc, mp, default, offkey in ctx.variants:
        if orig not in list(L.walk()):
            continue
        keys = list(mp.keys())
        if rng.random() < 0.15:
            key, chosen = offkey, default
        else:
            key = rng.choice(keys)
            chosen = mp[key]
        r["variants"][orig.id] = chosen
        r["entries"][(disc.id, ())] = {"kind": "move", "lit": _disc_lit(disc, key), "json": _disc_json(disc, key)}
    if ctx.odo is not None and ctx.odo in list(L.walk()):
        t = ctx.odo
        k = rng.randint(t.occurs["min"], t.occurs["max"])
        if rng.random() < 0.15:
            k = t.occurs["max"]
        elif rng.random() < 0.15:
            k = t.occurs["min"]
        r["count"] = k
        cnt = t.occurs["dep"]
        r["entries"][(cnt.id, ())] = {"kind": "move", "lit": _num_literal(k, 0), "json": canon(k, cnt.pic.scale)}
    _assign_children(ctx, r, L, ())
    return r


def _disc_lit(d, key):
    if d.pic.category == "alnum":
        return '"%s"' % key
    return key


def _disc_json(d, key):
    if d.pic.category == "alnum":
        return key.rstrip(" ")
    return canon(int(key), 0)


def _assign_children(ctx, r, g, subs):
    rng = ctx.rng
    for c in g.children:
        if c.redefines:
            continue
        if c.redefined_by:
            chosen = r["variants"].get(c.id, c) if c.id in r["variants"] else c
            if chosen is None:
                continue
            _assign_item(ctx, r, chosen, subs)
            continue
        _assign_item(ctx, r, c, subs)


def _assign_item(ctx, r, it, subs):
    rng = ctx.rng
    if it.occurs:
        n = it.occurs["max"]
        if it.occurs["dep"] is not None:
            n = r["count"]
        for k in range(1, n + 1):
            s2 = subs + (k,)
            if it.children:
                _assign_children(ctx, r, it, s2)
            else:
                _assign_elem(ctx, r, it, s2)
        return
    if it.children:
        _assign_children(ctx, r, it, subs)
        return
    _assign_elem(ctx, r, it, subs)


def _assign_elem(ctx, r, it, subs):
    rng = ctx.rng
    if it.filler:
        return
    if (it.id, subs) in r["entries"]:
        return
    if it.unset_p and rng.random() < it.unset_p:
        kinds = ["space", "space", "space", "low", "high"] if not ctx.opts["line_seq"] else ["space"]
        if r["init"] == "low":
            kinds = ["space", "low", "low", "high"]
        fill = rng.choice(kinds)
        r["entries"][(it.id, subs)] = {"kind": "fill", "fill": fill, "json": fill_expected(it, fill)}
        return
    lit, js = gen_value(ctx, it)
    r["entries"][(it.id, subs)] = {"kind": "move", "lit": lit, "json": js}


def expected_json(ctx, r):
    L = r["layout"]
    obj = {}
    _emit_children(ctx, r, L, (), obj)
    return obj


def _emit_children(ctx, r, g, subs, out):
    for c in g.children:
        if c.redefines:
            continue
        if c.redefined_by:
            if c.id in r["variants"]:
                chosen = r["variants"][c.id]
                if chosen is None:
                    continue
            else:
                chosen = c
            _emit_item(ctx, r, chosen, subs, out)
            continue
        _emit_item(ctx, r, c, subs, out)


def _emit_item(ctx, r, it, subs, out):
    if it.occurs:
        n = it.occurs["max"]
        if it.occurs["dep"] is not None:
            n = r["count"]
        arr = []
        for k in range(1, n + 1):
            s2 = subs + (k,)
            if it.children:
                o = {}
                _emit_children(ctx, r, it, s2, o)
                arr.append(o)
            else:
                arr.append(_elem_json(ctx, r, it, s2))
        if not it.filler:
            out[it.name] = arr
        return
    if it.children:
        if it.filler:
            _emit_children(ctx, r, it, subs, out)
            return
        o = {}
        _emit_children(ctx, r, it, subs, o)
        out[it.name] = o
        return
    if it.filler:
        return
    out[it.name] = _elem_json(ctx, r, it, subs)


def _elem_json(ctx, r, it, subs):
    e = r["entries"].get((it.id, subs))
    if e is None:
        # never moved: carries the record init fill
        return fill_expected(it, r["init"])
    return e["json"]
