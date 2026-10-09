"""Layout audit: for a case dir, compile its copybook under an FD with cobc and read the
offset of every elementary item (element 1, and element 2 of every enclosing table) via
pointer arithmetic; compare with the reference Layout. Runs inside the cobexp container:
  python3 /g/audit.py /out/cases/c0141 [...]
"""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, "/sol")
from unpack.copybook import parse_copybook
from unpack.layout import Layout, walk


def refs(it, subs_choices):
    """Yield (display-name, cobol-ref, my-offset) for elementary items under tables."""
    pass


def audit(cdir):
    meta = json.load(open(os.path.join(cdir, "case.json")))
    cpy = os.path.join(cdir, meta["copybook"])
    recs = parse_copybook(cpy)
    L = Layout(recs)
    # enumerate elementary items with subscript combos: (1,1,..) and each table dim at 2
    probes = []   # (label, cobol ref, expected offset)
    for r in recs:
        def rec(it, tables, base):
            # tables: list of enclosing OCCURS items; base: offset contribution of subs
            if it.children and not it.occurs:
                for c in it.children:
                    rec(c, tables, base)
                return
            if it.occurs:
                for c in (it.children or [it]):
                    if c is it:
                        _emit(it, tables + [it], base)
                    else:
                        rec(c, tables + [it], base)
                return
            _emit(it, tables, base)

        def _emit(it, tables, base):
            if it.name == "FILLER":
                return
            combos = [tuple([1] * len(tables))]
            for k in range(len(tables)):
                s = [1] * len(tables)
                s[k] = 2
                combos.append(tuple(s))
            for subs in combos:
                off = it.offset
                for t, s in zip(tables, subs):
                    off += (s - 1) * t.elem_size
                ref = it.name + ("(%s)" % " ".join(map(str, subs)) if subs else "")
                probes.append((ref, off, r.name))
        for c in r.children:
            rec(c, [], 0)
    src = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. AUD.", "ENVIRONMENT DIVISION.",
           "CONFIGURATION SECTION.", "SPECIAL-NAMES."]
    for sn in meta.get("special_names", []):
        src.append("    " + sn + ".")
    src += ["INPUT-OUTPUT SECTION.", "FILE-CONTROL.",
            '    SELECT OUTF ASSIGN TO "x.dat" ORGANIZATION IS %s.' % meta["organization"],
            "DATA DIVISION.", "FILE SECTION."]
    fdc = meta.get("fd", [])
    src.append("FD  OUTF" + ("." if not fdc else ""))
    for i, c in enumerate(fdc):
        src.append("    " + c + ("." if i == len(fdc) - 1 else ""))
    src.append('COPY "%s".' % os.path.basename(cpy))
    src += ["WORKING-STORAGE SECTION.", "01 WS-LEN PIC 9(5) COMP-5.",
            "01 PB USAGE POINTER.", "01 PN REDEFINES PB PIC 9(18) COMP-5.",
            "01 PX USAGE POINTER.", "01 PXN REDEFINES PX PIC 9(18) COMP-5.", "01 OFS PIC 9(6).",
            "PROCEDURE DIVISION."]
    # set every ODO count to max so subscripts are valid
    for r in recs:
        for it in walk(r):
            if it.occurs and it.occurs.get("depending"):
                src.append("MOVE %d TO %s." % (it.occurs["max"], it.occurs["depending"]))
    cur = None
    for i, (ref, off, rname) in enumerate(probes):
        if rname != cur:
            src.append("SET PB TO ADDRESS OF %s." % rname)
            cur = rname
        src.append('SET PX TO ADDRESS OF %s. COMPUTE OFS = PXN - PN. DISPLAY "P%d " OFS.' % (ref, i))
    src.append("STOP RUN.")
    # fixed format: every statement on its own line, area B, never past column 72
    fixed = []
    for ln in src:
        if ln.startswith("SET PX"):
            for part in ln.split(". "):
                part = part if part.endswith(".") else part + "."
                fixed.append("       " + part)
        else:
            if len(ln) > 65:
                raise SystemExit("line too long: " + ln)
            fixed.append("       " + ln)
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "aud.cob"), "w").write("\n".join(fixed) + "\n")
        p = subprocess.run(["cobc", "-x", "-I", cdir, "-o", os.path.join(td, "aud"), os.path.join(td, "aud.cob")],
                           capture_output=True, text=True, cwd=cdir)
        if p.returncode:
            print(cdir, "COMPILE FAIL", p.stderr[:1500]); return
        out = subprocess.run([os.path.join(td, "aud")], capture_output=True, text=True, cwd=td).stdout
    got = {}
    for ln in out.splitlines():
        m = re.match(r"P(\d+) (\d+)", ln)
        if m:
            got[int(m.group(1))] = int(m.group(2))
    bad = [(ref, off, got.get(i)) for i, (ref, off, rname) in enumerate(probes) if got.get(i) != off]
    print("%s: %d probes, %d mismatches" % (os.path.basename(cdir), len(probes), len(bad)))
    for ref, off, g in bad[:12]:
        print("   %-40s mine=%-6d cobc=%s" % (ref, off, g))
    return bad


if __name__ == "__main__":
    for d in sys.argv[1:]:
        audit(d)
