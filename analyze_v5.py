#!/usr/bin/env python3
"""Reference solver for license-reach (v2).

Reads only /app. For each third party component it decides, from the artifacts and the org's
own records, whether it is part of the delivered work AND carries a copyleft obligation that
CFS-DIST-4 leaves unmet. Writes {"disqualifying": [id,...]}.

Nothing is read off the SBOM's license column: the governing license is the SPDX tag in the
component's own source. Reach into the delivered work is forensic (nm defined symbols, DT_NEEDED,
dlopen strings, archive membership incl vendored code). A copyleft component that reaches the
delivered work is cleared only by (a) LGPL linked as a replaceable shared library, (b) a live
commercial grant that names it, covers the shipped version and has not expired at the ship date,
or (c) complete corresponding source published at the shipped version.
"""
import glob
import os
import re
import subprocess
import sys
import json


def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode(errors="replace")


def defined_syms(path):
    out = run(["nm", "--defined-only", "-g", path])
    syms = set()
    for line in out.splitlines():
        t = line.split()
        if len(t) >= 3 and re.fullmatch(r"[A-Za-z]", t[1]):
            syms.add(t[2])
        elif len(t) == 2 and t[0] in ("T", "D", "R", "W", "B", "t"):
            syms.add(t[1])
    return syms


def needed(path):
    return set(re.findall(r"Shared library:\s*\[([^\]]+)\]", run(["readelf", "-d", path])))


def has_string(path, needle):
    return needle in run(["strings", "-a", path])


PERMISSIVE = {"MIT", "BSD-3-Clause", "BSD-2-Clause", "Zlib", "Apache-2.0", "ISC"}


def kind(tok):
    base = tok.split(" WITH ")[0].strip()
    if "WITH" in tok and "exception" in tok.lower():
        return "exception"
    if base in PERMISSIVE:
        return "permissive"
    if base == "MPL-2.0":
        return "mpl"
    if base.startswith("LGPL"):
        return "lgpl"
    if base.startswith("AGPL"):
        return "agpl"
    if base.startswith("GPL"):
        return "gpl"
    return "unknown"


def effective(spdx):
    ks = [kind(b.strip()) for b in spdx.split(" OR ")]
    for pref in ("permissive", "exception", "mpl", "lgpl", "gpl", "agpl", "unknown"):
        if pref in ks:
            return pref
    return "unknown"


def spdx_tags(path):
    try:
        txt = open(path, errors="replace").read()
    except OSError:
        return []
    return re.findall(r"SPDX-License-Identifier:\s*([^\*\n\r]+?)\s*(?:\*/|$)", txt, re.M)


def source_funcs(cpath):
    return set(re.findall(r"\b([a-zA-Z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*\{",
                          open(cpath, errors="replace").read()))


def source_version(cdir):
    for c in glob.glob(os.path.join(cdir, "*.c")):
        m = re.search(r"/\*\s*version\s+([0-9][0-9.]*)\s*\*/", open(c, errors="replace").read())
        if m:
            return m.group(1)
    return None


def load_tsv(path, comma=False):
    sep = "," if comma else "\t"
    rows = [l.rstrip("\n").split(sep) for l in open(path) if l.strip()]
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def in_range(version, rng):
    if not version:
        return False
    v = vtuple(version)
    for cons in re.split(r"[,\s]+", rng.strip()):
        cons = cons.strip()
        if not cons:
            continue
        m = re.match(r"(>=|<=|>|<|==)\s*([0-9.]+)", cons)
        if not m:
            continue
        op, bound = m.group(1), vtuple(m.group(2))
        if op == ">=" and not v >= bound: return False
        if op == "<=" and not v <= bound: return False
        if op == ">" and not v > bound: return False
        if op == "<" and not v < bound: return False
        if op == "==" and not v == bound: return False
    return True


def analyze(root):
    comp_root = os.path.join(root, "components")
    ids = [os.path.basename(d) for d in glob.glob(os.path.join(comp_root, "*")) if os.path.isdir(d)]

    ship_date = "9999-99-99"
    rel = os.path.join(root, "RELEASE.txt")
    if os.path.isfile(rel):
        m = re.search(r"ship_date:\s*([\d-]+)", open(rel).read())
        if m:
            ship_date = m.group(1)

    grants_by_pid = {g["procurement_id"]: g for g in load_tsv(os.path.join(root, "procurement", "grants.csv"), comma=True)} \
        if os.path.isfile(os.path.join(root, "procurement", "grants.csv")) else {}
    pid_of_comp = {}
    catp = os.path.join(root, "procurement", "catalog.csv")
    if os.path.isfile(catp):
        for c in load_tsv(catp, comma=True):
            pid_of_comp.setdefault(c["component_id"], []).append(c["procurement_id"])
    published = {}
    pubp = os.path.join(root, "published_source.csv")
    if os.path.isfile(pubp):
        for p in load_tsv(pubp, comma=True):
            published[p["component_id"]] = p["published_version"]

    # delivered files: the two binaries, the shared objects they load, the plugins they open
    bins = sorted(glob.glob(os.path.join(root, "product", "bin", "*")))
    needed_names = set().union(*(needed(b) for b in bins)) if bins else set()
    loaded_libs = [p for p in glob.glob(os.path.join(root, "product", "lib", "*"))
                   if os.path.basename(p) in needed_names]
    loaded_plugins = [p for p in glob.glob(os.path.join(root, "product", "plugins", "*"))
                      if any(has_string(b, "plugins/" + os.path.basename(p)) for b in bins)]
    delivered = bins + loaded_libs + loaded_plugins
    present = set().union(*(defined_syms(f) for f in delivered)) if delivered else set()

    def owns_file(fname):
        for cid in ids:
            if glob.glob(os.path.join(comp_root, cid, "build", fname)):
                return cid
        return None
    dyn_comp = {owns_file(os.path.basename(p)) for p in loaded_libs} - {None}
    plugin_comp = {owns_file(os.path.basename(p)) for p in loaded_plugins} - {None}

    def grant_ok(cid, version):
        for pid in pid_of_comp.get(cid, []):
            g = grants_by_pid.get(pid)
            if g and in_range(version, g["covers_version_range"]) and g["expires_on"] > ship_date:
                return True
        return False

    def published_ok(cid, version):
        return published.get(cid) == version

    findings = []
    for cid in ids:
        cdir = os.path.join(comp_root, cid)
        version = source_version(cdir)

        # governing licenses of this component's code, and of code it vendored
        own_tags = []
        for c in glob.glob(os.path.join(cdir, "*.c")):
            own_tags += spdx_tags(c)
        own_spdx = own_tags[0] if own_tags else "MIT"
        vendored = []  # (spdx, symbols)
        for sub in glob.glob(os.path.join(cdir, "**", "*.c"), recursive=True):
            if os.path.dirname(sub) == cdir:
                continue
            tags = spdx_tags(sub)
            if tags:
                vendored.append((tags[0], source_funcs(sub)))

        # what this component contributes, and how it reaches the delivered work
        csyms = set()
        for art in glob.glob(os.path.join(cdir, "build", "*")):
            csyms |= defined_syms(art)
        present_here = csyms & present

        reach = None
        if cid in dyn_comp:
            reach = "dynamic"
        elif cid in plugin_comp:
            reach = "plugin"
        elif present_here:
            reach = "static"
        # else: exec program / build tool / internal tool -> not part of delivered work

        if reach is None:
            continue

        # every governing license that actually reaches the delivered work
        govern = []
        if reach in ("dynamic", "plugin"):
            govern.append(own_spdx)
        else:  # static: the licenses of the symbols that are present
            vsyms = set().union(*(s for _l, s in vendored)) if vendored else set()
            for lspdx, syms in vendored:
                if syms & present_here:
                    govern.append(lspdx)
            if present_here - vsyms:
                govern.append(own_spdx)

        disq = False
        for lspdx in govern:
            k = effective(lspdx)
            if k not in ("gpl", "agpl", "lgpl"):
                continue                                   # permissive / exception / mpl / dual-perm
            if k == "lgpl" and reach == "dynamic":
                continue                                   # relinkable shared library
            if grant_ok(cid, version) or published_ok(cid, version):
                continue                                   # covered by grant or published source
            disq = True
        if disq:
            findings.append(cid)

    return sorted(findings)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "/app"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "findings.json")
    result = {"disqualifying": analyze(root)}
    json.dump(result, open(out, "w"), indent=2)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
