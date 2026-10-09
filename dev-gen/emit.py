"""Emit copybook text (in varied real-world styles) and the GnuCOBOL writer program."""

import random

from ast_gen import G, elem_bytes

LEVEL_SCHEMES = [[1, 5, 10, 15, 20, 25, 30], [1, 3, 5, 7, 9, 11, 13], [1, 2, 3, 4, 5, 6, 7],
                 [1, 5, 7, 10, 12, 15, 17], [1, 5, 10, 15, 20, 25, 30], [1, 3, 5, 10, 15, 20, 25]]


class Style:
    def __init__(self, rng):
        self.rng = rng
        self.levels = rng.choice(LEVEL_SCHEMES)
        self.indent = rng.choice([2, 2, 3, 4])
        self.seq = rng.choice(["none", "none", "num", "num", "tag"])
        self.idarea = rng.choice(["none", "none", "none", "tag", "mixed"])
        self.lower = rng.random() < 0.15
        self.longforms = rng.random() < 0.3
        self.multiline_p = rng.choice([0.0, 0.1, 0.3, 0.6])
        self.comments_p = rng.choice([0.0, 0.1, 0.25])
        self.name_col = rng.choice([0, 1, 2])   # extra spaces between level and name
        self.pic_col = rng.choice([None, 32, 36, 40])
        self.period_own_line = rng.random() < 0.05
        self.float_comment_p = 0.1 if rng.random() < 0.3 else 0.0
        self.blank_p = rng.choice([0.0, 0.05, 0.15])
        self.debug_lines = rng.random() < 0.12
        self.tag = rng.choice(["CHG0021", "REL2019", "TKT4471", "MIG0007", "A1B2C3D4", "COPYBK01"])
        self.base_indent = rng.choice([0, 0, 4, 4, 1, 3])
        self.seqno = 0


def _word(style, w):
    return w.lower() if style.lower else w


class Emitter:
    def __init__(self, ctx, style):
        self.ctx = ctx
        self.rng = ctx.rng
        self.style = style
        self.features = ctx.features
        self.files = {}    # filename -> list of lines

    # ---- physical line assembly
    def line(self, out, text, indicator=" ", idtag=None):
        st = self.style
        if st.seq == "num":
            st.seqno += 100 if self.rng.random() < 0.9 else 10
            seq = "%06d" % (st.seqno % 1000000)
        elif st.seq == "tag":
            seq = (st.tag[:4] + "%02d" % (st.seqno % 100))
            st.seqno += 1
        else:
            seq = " " * 6 if self.rng.random() < 0.8 else ""
        if len(text) > 65:
            raise ValueError("text area overflow: %r" % text)
        if st.idarea == "none" and idtag is None:
            body = (seq + indicator + text).rstrip() if seq else (" " * 6 + indicator + text).rstrip()
            if not seq:
                body = ("      " + indicator + text).rstrip()
            out.append(body)
            return
        tag = idtag if idtag is not None else (st.tag if st.idarea == "tag" or self.rng.random() < 0.5 else "")
        if not seq:
            seq = " " * 6
        out.append((seq + indicator + text.ljust(65) + tag).rstrip())

    def comment(self, out, text, ind="*"):
        self.line(out, " " + text[:64], indicator=ind)

    # ---- entries
    def level_no(self, depth):
        lv = self.style.levels
        if depth < len(lv):
            return lv[depth]
        return lv[-1] + (depth - len(lv) + 1)

    def emit_record(self, root, out, depth=0, level_override=None, sub_prefix=None):
        st = self.style
        rng = self.rng
        self.emit_entry(root, out, depth, level_override, sub_prefix)
        for c in root.children:
            if c.copy and sub_prefix is None:
                self.emit_copy(c, out, depth + 1)
                continue
            self.emit_record(c, out, depth + 1, None, sub_prefix)
            if rng.random() < st.blank_p:
                out.append("")
            if rng.random() < st.comments_p:
                self.random_comment(out)

    def random_comment(self, out):
        rng = self.rng
        st = self.style
        t = rng.choice([
            "05  OLD-%s-FIELD  PIC X(10).  removed %d" % (rng.choice(["ACCT", "CUST", "REF"]), rng.randint(2004, 2023)),
            "-- reserved for future use --",
            "note: PIC S9(7)V99 COMP-3 was PIC 9(9) before %d" % rng.randint(2001, 2020),
            "10 FILLER PIC X(20). *> dropped",
            "layout verified against copy member %s" % st.tag,
            "changes: %s" % st.tag,
            "*** do not reorder these fields ***",
            "occurs 12 times in the legacy version",
            "COPY WSHDR. (retired)",
        ])
        self.comment(out, t, ind=rng.choice(["*", "*", "*", "/"]))
        if st.debug_lines and rng.random() < 0.5:
            self.features.add("debug-line")
            self.line(out, "    %02d  DBG-%s PIC X(%d)." % (self.level_no(1), rng.choice(["TRACE", "MARK", "SEQ"]), rng.randint(1, 8)), indicator="D")

    def name_of(self, it, sub_prefix):
        if it.filler:
            return "FILLER"
        n = it.name
        if sub_prefix is not None:
            pre, tag = sub_prefix
            if n.startswith(pre + "-"):
                n = ":%s:" % tag + n[len(pre):]
            elif n == pre:
                n = ":%s:" % tag
        return n

    def clauses(self, it, sub_prefix):
        st = self.style
        rng = self.rng
        cl = []
        if it.redefines is not None:
            cl.append("REDEFINES " + self.name_of(it.redefines, sub_prefix))
        rest = []
        if it.pic_text:
            pic = it.pic_text
            if sub_prefix is not None and getattr(it, "len_tag", None):
                pic = it.len_tag_pic
            kw = "PICTURE IS" if (st.longforms and rng.random() < 0.6) else ("PICTURE" if rng.random() < 0.1 else "PIC")
            if rng.random() < 0.15 and not st.longforms:
                kw = "PIC IS"
            rest.append(kw + " " + pic)
        if it.usage:
            u = it.usage
            if st.longforms and rng.random() < 0.5:
                rest.append("USAGE IS " + u)
            elif rng.random() < 0.2:
                rest.append("USAGE " + u)
            else:
                rest.append(u)
        if it.sign:
            d, sep = it.sign
            forms = ["SIGN IS %s%s" % (d, " SEPARATE CHARACTER" if sep else ""),
                     "SIGN %s%s" % (d, " SEPARATE" if sep else ""),
                     "%s%s" % (d, " SEPARATE" if sep else "")]
            rest.append(rng.choice(forms))
        if it.occurs:
            o = it.occurs
            if o["dep"] is not None:
                s = "OCCURS %d TO %d TIMES DEPENDING ON %s" % (o["min"], o["max"], self.name_of(o["dep"], sub_prefix))
                if rng.random() < 0.3:
                    s = s.replace(" TIMES", "").replace("DEPENDING ON", "DEPENDING")
            else:
                s = "OCCURS %d TIMES" % o["max"] if rng.random() < 0.8 else "OCCURS %d" % o["max"]
            unit = [s]
            if o.get("key"):
                keyf = next((c for c in it.children if not c.children and not c.filler), None)
                if keyf is not None:
                    unit.append(("ASCENDING KEY IS " if rng.random() < 0.5 else "DESCENDING KEY ") + self.name_of(keyf, sub_prefix))
            if o.get("indexed"):
                unit.append("INDEXED BY " + self.ctx.namer.name(self.ctx.prefix, 1).replace(self.ctx.prefix, rng.choice(["IX", "IDX", "I"])))
            rest.append(unit)
        if it.sync:
            rest.append(rng.choice(["SYNC", "SYNC", "SYNCHRONIZED"]))
        if it.just:
            rest.append(rng.choice(["JUST", "JUST RIGHT", "JUSTIFIED RIGHT", "JUSTIFIED"]))
        if it.bwz:
            rest.append(rng.choice(["BLANK WHEN ZERO", "BLANK ZERO", "BLANK WHEN ZEROS", "BLANK WHEN ZEROES"]))
        if it.value:
            v = it.value
            if v == ["LONGLIT"]:
                rest.append("VALUE " + self.long_literal(it.pic.size))
            else:
                kw = rng.choice(["VALUE", "VALUE IS", "VALUE"])
                rest.append(kw + " " + " ".join(v))
        rng.shuffle(rest)
        flat = []
        for r in rest:
            if isinstance(r, list):
                flat.extend(r)
            else:
                flat.append(r)
        return cl + flat

    def long_literal(self, n):
        # marker consumed by emit_entry: '\x01<len>'
        return "\x01%d" % n

    def emit_entry(self, it, out, depth, level_override=None, sub_prefix=None):
        st = self.style
        rng = self.rng
        lvl = level_override if level_override is not None else self.level_no(depth)
        ind = " " * (self.style.indent * depth) if depth else ""
        nm = self.name_of(it, sub_prefix)
        head = ind + "%02d" % lvl + " " * (1 + st.name_col)
        if nm == "FILLER" and rng.random() < 0.3 and not it.children:
            head = head.rstrip()
        else:
            head += nm
        head = _word(st, head)
        cls = self.clauses(it, sub_prefix)
        if st.lower:
            cls = [self._lower_keep_lits(c) for c in cls]
        cont = None
        for i, c in enumerate(cls):
            if "\x01" in c:
                n = int(c.split("\x01")[1])
                lit = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ ") for _ in range(n))
                first = lit[: max(5, min(30, n - 5))]
                cls[i] = c.split("\x01")[0] + "'" + first
                cont = "'" + lit[len(first):] + "'"
                self.features.add("continuation")
        if cont is not None:
            # the open literal must end its line: make it the last clause
            open_idx = next(i for i, c in enumerate(cls) if c.count("'") % 2 == 1)
            cls.append(cls.pop(open_idx))
        limit = self.max_text()
        if not cls:
            self._emit_text(out, head + ".")
            return
        multiline = rng.random() < st.multiline_p
        lines = []
        cur = head
        pad_pic = st.pic_col
        first = True
        cind = " " * (len(ind) + st.indent + 4)
        for c in cls:
            gap = " "
            if first and pad_pic and len(head) < pad_pic - 1 and c.upper().startswith("PIC"):
                gap = " " * (pad_pic - 1 - len(head))
            first = False
            cand = cur + gap + c
            if len(cand) <= limit - 1 and not (multiline and cur != head and rng.random() < 0.5) \
                    and not (multiline and cur == head and rng.random() < 0.3):
                cur = cand
            else:
                lines.append(cur)
                cur = cind + c
                if len(cur) > limit - 1:
                    # split a long clause at spaces (never inside a literal)
                    words = c.split(" ")
                    cur = cind + words[0]
                    for w in words[1:]:
                        if len(cur) + 1 + len(w) <= limit - 1:
                            cur += " " + w
                        else:
                            lines.append(cur)
                            cur = cind + w
        lines.append(cur)
        if cont is not None:
            for ln in lines:
                self._emit_text(out, ln)
            self.line(out, "    " + cont + ".", indicator="-")
            return
        if st.period_own_line and rng.random() < 0.5:
            for ln in lines:
                self._emit_text(out, ln)
            self._emit_text(out, ind + "    .")
            return
        lines[-1] += "."
        for ln in lines:
            self._emit_text(out, ln)

    def _lower_keep_lits(self, c):
        out = []
        q = None
        for ch in c:
            if q:
                out.append(ch)
                if ch == q:
                    q = None
            elif ch in "'\"":
                q = ch
                out.append(ch)
            else:
                out.append(ch.lower())
        return "".join(out)

    def max_text(self):
        return 65 - self.style.base_indent

    def _emit_text(self, out, text):
        st = self.style
        rng = self.rng
        if len(text) > self.max_text():
            raise ValueError("line too long: %r" % text)
        if st.float_comment_p and rng.random() < st.float_comment_p and len(text) < self.max_text() - 14:
            text = text + " *> " + rng.choice(["key", "see spec", "eff 2021", "was X(8)", "cf. copybook"])
            self.features.add("float-comment")
            text = text[:self.max_text()]
        self.line(out, " " * st.base_indent + text)

    def emit_88s(self, it, out, depth, sub_prefix):
        for nm, vals in it.conds:
            lvl = "88"
            n = self.name_of(G(nm), sub_prefix)
            kw = self.rng.choice(["VALUE", "VALUES", "VALUE IS", "VALUES ARE"])
            text = " " * (self.style.indent * (depth + 1)) + lvl + " " + n + " " + kw + " " + " ".join(vals) + "."
            text = _word(self.style, text) if not self.style.lower else self._lower_keep_lits(text)
            if len(text) > 61:
                text = " " * (self.style.indent * (depth + 1)) + lvl + " " + n + " " + kw + " " + vals[0] + "."
            self._emit_text(out, text)

    def emit_copy(self, g, out, depth):
        rng = self.rng
        base, tag, literal_form = g.copy
        fname = base + ".cpy" if literal_form else base + rng.choice([".cpy", ".cpy", ".CPY"])
        sub = []
        if rng.random() < 0.6:
            self.comment(sub, " %s - shared block, prefix is :%s:" % (base, tag))
        self.emit_record_sub(g, sub, depth, (self.ctx.prefix, tag))
        self.files[fname] = sub
        rep = "==:%s:== BY ==%s==" % (tag, self.ctx.prefix)
        if literal_form:
            head = 'COPY "%s"' % fname
        else:
            head = "COPY %s" % base
        ind = " " * (self.style.indent * depth)
        if rng.random() < 0.5:
            self._emit_text(out, ind + head + " REPLACING " + rep + ".")
        else:
            self._emit_text(out, ind + head)
            self._emit_text(out, ind + "     REPLACING " + rep + ".")

    def emit_record_sub(self, root, out, depth, sub_prefix):
        self.emit_entry(root, out, depth, None, sub_prefix)
        self.emit_88s(root, out, depth, sub_prefix)
        for c in root.children:
            self.emit_record_sub(c, out, depth + 1, sub_prefix)

    # ---- whole copybook
    def emit_copybook(self, records):
        rng = self.rng
        st = self.style
        out = []
        if rng.random() < 0.7:
            self.comment(out, "*" * 62)
            self.comment(out, "  %s  -  %s" % (self.ctx.prefix, rng.choice(["MASTER RECORD LAYOUT", "TRANSACTION RECORD", "EXTRACT LAYOUT", "INTERFACE RECORD", "HISTORY FILE RECORD"])))
            if rng.random() < 0.5:
                self.comment(out, "  last change %s  %s" % (st.tag, rng.choice(["JRL", "MKD", "TPS", "AVH"])))
            self.comment(out, "*" * 62)
        for L in records:
            self.emit_tree(L, out, 0)
            if getattr(L, "renames", False):
                self.emit_renames(L, out)
        return out

    def emit_tree(self, it, out, depth, sub_prefix=None):
        st = self.style
        rng = self.rng
        if it.copy and sub_prefix is None:
            self.emit_copy(it, out, depth)
            return
        self.emit_entry(it, out, depth, None, sub_prefix)
        self.emit_88s(it, out, depth, sub_prefix)
        for c in it.children:
            self.emit_tree(c, out, depth + 1, sub_prefix)
            if rng.random() < st.blank_p:
                out.append("")
            if rng.random() < st.comments_p:
                self.random_comment(out)

    def emit_renames(self, L, out):
        cands = [c for c in L.children if not c.occurs and not c.redefines and not c.redefined_by
                 and not c.copy and not c.is_count and (not c.children or True)]
        cands = [c for c in cands if not any(x.occurs for x in c.walk())]
        if len(cands) < 2:
            return
        i = self.rng.randrange(0, len(cands) - 1)
        a, b = cands[i], cands[i + 1]
        nm = self.ctx.namer.name(self.ctx.prefix, 1)
        if self.rng.random() < 0.7:
            text = "66 %s RENAMES %s THRU %s." % (nm, a.name, b.name)
        else:
            text = "66 %s RENAMES %s." % (nm, a.name)
        if len(text) > 61:
            text = "66 %s RENAMES %s." % (nm, a.name)
        self._emit_text(out, _word(self.style, text))
        self.features.add("renames")


# --------------------------------------------------------------------------- writer

def cob_line(text):
    if len(text) > 65:
        raise ValueError("cobol line too long: %r" % text)
    return "       " + text


def cob_stmt(L, text):
    """Append a statement, wrapping at ' TO ' / ' OF ' word boundaries when needed."""
    if len(text) <= 65:
        L.append(cob_line(text))
        return
    words = text.split(" ")
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= 65:
            cur += " " + w
        else:
            L.append(cob_line(cur))
            cur = "      " + w
    L.append(cob_line(cur))


def emit_writer(ctx, records_vals, case_meta):
    """records_vals: list of assignment dicts from ast_gen.assign_record."""
    rng = ctx.rng
    L = []
    L.append(cob_line("IDENTIFICATION DIVISION."))
    L.append(cob_line("PROGRAM-ID. WRITER."))
    L.append(cob_line("ENVIRONMENT DIVISION."))
    L.append(cob_line("CONFIGURATION SECTION."))
    L.append(cob_line("SPECIAL-NAMES."))
    for sn in case_meta.get("special_names", []):
        L.append(cob_line("    " + sn + "."))
    L.append(cob_line("INPUT-OUTPUT SECTION."))
    L.append(cob_line("FILE-CONTROL."))
    L.append(cob_line('    SELECT OUTF ASSIGN TO "data.dat"'))
    L.append(cob_line("      ORGANIZATION IS %s." % case_meta["organization"]))
    L.append(cob_line("DATA DIVISION."))
    L.append(cob_line("FILE SECTION."))
    fdc = case_meta.get("fd", [])
    if not fdc:
        L.append(cob_line("FD  OUTF."))
    else:
        L.append(cob_line("FD  OUTF"))
        for i, c in enumerate(fdc):
            L.append(cob_line("    " + c + ("." if i == len(fdc) - 1 else "")))
    L.append(cob_line('COPY "%s".' % case_meta["copybook"]))
    L.append(cob_line("WORKING-STORAGE SECTION."))
    L.append(cob_line("01  WS-LEN PIC 9(5) COMP-5."))
    L.append(cob_line("LINKAGE SECTION."))
    L.append(cob_line("01  LS-BYTES PIC X(65535)."))
    L.append(cob_line("PROCEDURE DIVISION."))
    L.append(cob_line("    OPEN OUTPUT OUTF."))
    init_word = {"space": "SPACES", "low": "LOW-VALUES"}
    dep = any("DEPENDING ON WS-LEN" in c for c in case_meta.get("fd", []))
    for r in records_vals:
        root = r["layout"]
        if r["count"] is not None:
            t = ctx.odo
            cob_stmt(L, "    MOVE %d TO %s." % (t.occurs["max"], t.occurs["dep"].name))
        cob_stmt(L, "    MOVE %s TO %s." % (init_word[r["init"]], root.name))
        if r["count"] is not None:
            cob_stmt(L, "    MOVE %d TO %s." % (r["count"], ctx.odo.occurs["dep"].name))
        # emit moves in a stable order: sorted by item id then subs
        items = {it.id: it for it in root.walk()}
        for (iid, subs), e in sorted(r["entries"].items(), key=lambda kv: (kv[0][0], kv[0][1])):
            it = items.get(iid)
            if it is None:
                continue
            if it.is_count and r["count"] is not None and it is ctx.odo.occurs["dep"]:
                continue
            ref = it.name + ("(%s)" % " ".join(str(s) for s in subs) if subs else "")
            if e["kind"] == "fill":
                cob_stmt(L, "    SET ADDRESS OF LS-BYTES TO ADDRESS OF %s." % ref)
                cob_stmt(L, "    MOVE %s TO LS-BYTES(1:%d)." % (
                    {"space": "SPACES", "low": "LOW-VALUES", "high": "HIGH-VALUES"}[e["fill"]], elem_bytes(it)))
                continue
            lit = e["lit"]
            if lit == '""':
                lit = "SPACES" if (it.pic is not None and it.pic.category in ("alnum", "alnum_edited")) else '" "'

            if lit.startswith('"'):
                # never split inside a literal
                if len("    MOVE " + lit + " TO " + ref + ".") <= 65:
                    L.append(cob_line("    MOVE " + lit + " TO " + ref + "."))
                else:
                    L.append(cob_line("    MOVE " + lit))
                    cob_stmt(L, "      TO " + ref + ".")
            else:
                cob_stmt(L, "    MOVE " + lit + " TO " + ref + ".")
        if dep:
            cob_stmt(L, "    MOVE LENGTH OF %s TO WS-LEN." % root.name)
        cob_stmt(L, "    WRITE %s." % root.name)
    L.append(cob_line("    CLOSE OUTF."))
    L.append(cob_line("    STOP RUN."))
    return "\n".join(L) + "\n"
