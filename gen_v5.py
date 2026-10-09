#!/usr/bin/env python3
"""Generate the license-reach bundle (v2, hardened).

A real toolchain-built proprietary product (real ELF binaries, static .a archives, shared .so,
dlopen plugins, an exec'd program) whose distributability is decided NOT by textbook copyleft
rules but by a bespoke org policy (CFS-DIST-4) that overrides them, applied against evidence that
is indirect and partly wrong:

  - the SBOM's license column is administrative and wrong for some components; the governing
    license is the SPDX tag in the component's own source.
  - a copyleft component reaching the delivered work is cleared ONLY by a live commercial grant
    (right component, shipped version inside the grant's range, term not expired at the ship date)
    OR by the org publishing its complete corresponding source (on the register AND at the shipped
    version, not a stale one). knowing "GPL static = bad" both over- and under-shoots.
  - plus the real linkage forensics: static-in-binary vs a replaceable shared library vs a dlopen
    plugin vs an exec'd separate program vs build-only vs internal, an archive member the linker
    never pulled in, and a permissive wrapper that vendored copyleft code that reached the binary.

The disqualifying set is re-derived by solution/analyze.py from /app alone; the two must agree.

Run:  python3 dev/gen.py <out_app_dir> <out_answer_json>
"""
import json
import os
import subprocess
import sys
import textwrap

SHIP_DATE = "2026-09-10"

LICENSE_TEXT = {
    "MIT": "MIT License. Permission is hereby granted, free of charge... (permissive).\n",
    "Zlib": "zlib License. This software is provided 'as-is'... (permissive).\n",
    "BSD-3-Clause": "BSD 3-Clause License. Redistribution and use... (permissive).\n",
    "LGPL-2.1-only": "GNU LESSER GENERAL PUBLIC LICENSE 2.1. A combined work may be conveyed "
                     "under terms of your choice if you allow modification of the Library portion "
                     "and reverse engineering, e.g. by supplying relinkable object code.\n",
    "GPL-2.0-only": "GNU GENERAL PUBLIC LICENSE Version 2. Distribution of a work containing or "
                    "derived from the Program requires licensing the whole under this License and "
                    "giving all recipients the corresponding source.\n",
    "GPL-3.0-only": "GNU GENERAL PUBLIC LICENSE Version 3. You must convey the Corresponding "
                    "Source under this License to anyone who receives the object code.\n",
    "AGPL-3.0-only": "GNU AFFERO GPL Version 3. All GPLv3 terms; conveying a covered work requires "
                     "giving recipients the Corresponding Source.\n",
    "MPL-2.0": "Mozilla Public License 2.0. Applies file by file; Covered Software (the MPL files) "
               "may be combined with other code under other terms; the Source of the Covered files "
               "must be made available.\n",
    "GPL-2.0-only WITH GCC-exception-2.0": "GPLv2 WITH a linking exception: you may link this "
        "library with independent modules and distribute the executable under terms of your "
        "choice, with no GPL requirement on the independent modules.\n",
    "GPL-2.0-only OR BSD-3-Clause": None,
}

# component table. fields:
#   id, sbom_spdx (what the SBOM claims), true_spdx (SPDX tag in the source),
#   sym, target (reporter|collector), linkage, version,
#   grant=(proc_id, version_range, expires) | None, published=version | None, disq
# Component ids are opaque, realistic library names that do NOT reveal the verdict. Nothing about
# how a component is wired in is stated anywhere: linkage is determined only from the artifacts.
COMPONENTS = [
    # id            sbom_spdx                              true_spdx                              sym   target      linkage         ver    grant                                    pub    disq
    ("flatjson",    "MIT",                                 "MIT",                                 "fj", "reporter", "dynamic",      "1.2", None,                                    None,  False),
    ("deflate9",    "Zlib",                                "Zlib",                                "df", "collector","static",       "1.0", None,                                    None,  False),
    ("cryptoline",  "BSD-3-Clause",                        "BSD-3-Clause",                        "cl", "reporter", "dynamic",      "3.1", None,                                    None,  False),
    ("fmtplug",     "BSD-3-Clause",                        "BSD-3-Clause",                        "fp", "reporter", "dlopen",       "0.9", None,                                    None,  False),
    ("statgrid",    "GPL-2.0-only",                        "GPL-2.0-only",                        "sg", "reporter", "static",       "4.0", None,                                    None,  True),
    ("rowstore",    "LGPL-2.1-only",                       "LGPL-2.1-only",                       "rs", "collector","static",       "2.2", None,                                    None,  True),
    ("parsekit",    "LGPL-2.1-only",                       "LGPL-2.1-only",                       "pk", "reporter", "dynamic",      "1.5", None,                                    None,  False),
    ("glyphrender", "GPL-2.0-only",                        "GPL-2.0-only",                        "gr", "reporter", "dynamic",      "1.1", None,                                    None,  True),
    ("probeplug",   "GPL-2.0-only",                        "GPL-2.0-only",                        "pp", "reporter", "dlopen",       "0.5", None,                                    None,  True),
    ("netframe",    "AGPL-3.0-only",                       "AGPL-3.0-only",                       "nf", "collector","static",       "5.0", None,                                    None,  True),
    ("lictrack",    "GPL-2.0-only",                        "GPL-2.0-only",                        "lk", "reporter", "static",       "1.4", ("PROC-11", ">=1.0 <2.0", "2027-01-01"), None,  False),
    ("sessioncache","GPL-2.0-only",                        "GPL-2.0-only",                        "sc", "collector","static",       "3.0", ("PROC-12", ">=1.0 <9.0", "2026-06-01"), None,  True),
    ("polymath",    "GPL-2.0-only",                        "GPL-2.0-only",                        "pm", "reporter", "static",       "2.3", ("PROC-13", ">=1.0 <2.0", "2027-01-01"), None,  True),
    ("vectorize",   "GPL-2.0-only",                        "GPL-2.0-only",                        "vz", "reporter", "static",       "3.2", None,                                    "3.2", False),
    ("archindex",   "GPL-2.0-only",                        "GPL-2.0-only",                        "ax", "collector","static",       "2.5", None,                                    "2.0", True),
    ("csvlite",     "MIT",                                 "GPL-2.0-only",                        "cv", "reporter", "static",       "1.0", None,                                    None,  True),
    ("xmlmini",     "GPL-2.0-only",                        "MIT",                                 "xm", "reporter", "static",       "1.0", None,                                    None,  False),
    ("linefmt",     "GPL-2.0-only",                        "GPL-2.0-only",                        "lf", "reporter", "static-unref", "1.0", None,                                    None,  False),
    ("tablegen",    "GPL-3.0-only",                        "GPL-3.0-only",                        "tg", "reporter", "build",        "1.0", None,                                    None,  False),
    ("imgtool",     "GPL-2.0-only",                        "GPL-2.0-only",                        "it", "collector","exec",         "1.0", None,                                    None,  False),
    ("statsprobe",  "AGPL-3.0-only",                       "AGPL-3.0-only",                       "sp", "ingest",   "internal",     "1.0", None,                                    None,  False),
    ("mathchoice",  "GPL-2.0-only OR BSD-3-Clause",        "GPL-2.0-only OR BSD-3-Clause",        "ma", "reporter", "static",       "1.0", None,                                    None,  False),
    ("compatlink",  "GPL-2.0-only WITH GCC-exception-2.0", "GPL-2.0-only WITH GCC-exception-2.0", "co", "collector","static",       "1.0", None,                                    None,  False),
    ("codecfile",   "MPL-2.0",                             "MPL-2.0",                             "cd", "reporter", "static",       "1.0", None,                                    None,  False),
    ("hashwell",    "MIT",                                 "MIT",                                 "hw", "collector","chain",        "1.0", None,                                    None,  True),
]

ANSWER = sorted(c[0] for c in COMPONENTS if c[9])
BY = {c[0]: c for c in COMPONENTS}


def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.stderr.write(r.stdout.decode())
        raise SystemExit(f"command failed: {' '.join(cmd)}")
    return r.stdout.decode()


def spdx_header(spdx):
    tag = spdx.split(" OR ")[0] if " OR " in spdx else spdx
    return f"/* SPDX-License-Identifier: {spdx} */\n"


def body(sym, spdx, version):
    return (spdx_header(spdx) +
            f"/* version {version} */\n"
            f"int {sym}_fn(int x){{ return (x ^ 0x{abs(hash(sym)) & 0xffff:04x}) + {len(sym)}; }}\n")


def build(root):
    comp = os.path.join(root, "components")
    prod = os.path.join(root, "product")
    for d in (comp, os.path.join(prod, "bin"), os.path.join(prod, "lib"),
              os.path.join(prod, "plugins"), os.path.join(prod, "tools")):
        os.makedirs(d, exist_ok=True)
    B = os.path.join(root, ".build")
    os.makedirs(B, exist_ok=True)

    def cdir(cid):
        d = os.path.join(comp, cid)
        os.makedirs(d, exist_ok=True)
        return d

    def write_license(cid, spdx):
        d = cdir(cid)
        if spdx == "GPL-2.0-only OR BSD-3-Clause":
            open(os.path.join(d, "LICENSE.GPL-2.0"), "w").write(LICENSE_TEXT["GPL-2.0-only"])
            open(os.path.join(d, "LICENSE.BSD-3"), "w").write(LICENSE_TEXT["BSD-3-Clause"])
        else:
            open(os.path.join(d, "LICENSE"), "w").write(LICENSE_TEXT[spdx])

    def write_src(cid, sym, true_spdx, version):
        p = os.path.join(cdir(cid), f"{cid.replace('-', '_')}.c")
        open(p, "w").write(body(sym, true_spdx, version))
        return p

    def obj(cid, sym, true_spdx, version, fpic=True):
        p = write_src(cid, sym, true_spdx, version)
        o = os.path.join(B, f"{cid}.o")
        flags = ["-O2"] + (["-fPIC"] if fpic else [])
        sh(["gcc"] + flags + ["-c", p, "-o", o])
        return o

    def archive(cid, members):
        d = os.path.join(cdir(cid), "build")
        os.makedirs(d, exist_ok=True)
        ap = os.path.join(d, f"lib{cid.replace('-', '_')}.a")
        sh(["ar", "rcs", ap] + members)
        return ap

    def shared(cid, o, soname):
        d = os.path.join(cdir(cid), "build")
        os.makedirs(d, exist_ok=True)
        sp = os.path.join(d, soname)
        sh(["gcc", "-shared", "-o", sp, o, "-Wl,-soname," + soname])
        return sp

    static_a, dyn_so = {}, {}
    reporter_static, collector_static = [], []          # archives to place on each link line
    reporter_calls, collector_calls = [], []            # (sym) referenced
    reporter_dyn, collector_dyn = [], []                # (soname) DT_NEEDED
    reporter_dlopen = []                                 # (component, plugin_name, sym)

    for (cid, sbom_spdx, true_spdx, sym, target, linkage, version, grant, pub, disq) in COMPONENTS:
        write_license(cid, true_spdx)
        if linkage in ("static", "static-unref"):
            o = obj(cid, sym, true_spdx, version)
            static_a[cid] = archive(cid, [o])
            if target == "reporter":
                reporter_static.append(static_a[cid])
                if linkage == "static":
                    reporter_calls.append(sym)
            else:
                collector_static.append(static_a[cid])
                if linkage == "static":
                    collector_calls.append(sym)
        elif linkage == "dynamic":
            o = obj(cid, sym, true_spdx, version)
            soname = f"lib{cid.replace('-', '_')}.so.1"
            dyn_so[cid] = shared(cid, o, soname)
            sh(["cp", dyn_so[cid], os.path.join(prod, "lib", soname)])
            if target == "reporter":
                reporter_dyn.append(soname); reporter_calls.append(sym)
        elif linkage == "dlopen":
            o = obj(cid, sym, true_spdx, version)
            pname = f"{cid.replace('-', '_')}.so"
            sp = shared(cid, o, pname)
            sh(["cp", sp, os.path.join(prod, "plugins", pname)])
            reporter_dlopen.append((cid, pname, sym))
        elif linkage == "exec":
            write_src(cid, sym, true_spdx, version)
            # a real standalone program the delivered binary runs as a child process
            main_c = os.path.join(B, f"{cid}_main.c")
            open(main_c, "w").write(spdx_header(true_spdx) +
                                    f'#include <stdio.h>\nint main(void){{printf("{cid} ok\\n");return 0;}}\n')
            sh(["gcc", "-O2", main_c, "-o", os.path.join(prod, "tools", cid)])
        elif linkage == "build":
            # the component's source IS the generator; only its emitted data reaches reporter
            rg = os.path.join(B, "reportgen")
            main_c = os.path.join(cdir(cid), f"{cid.replace('-', '_')}.c")
            open(main_c, "w").write(spdx_header(true_spdx) + f"/* version {version} */\n" +
                '/* build-time table generator: writes gen_table.c, a pure data table, to stdout */\n'
                '#include <stdio.h>\nint main(void){printf("const int gen_table[8]={");'
                'for(int i=0;i<8;i++)printf("%d,",(i*97+13)%251);printf("};\\n");return 0;}\n')
            sh(["gcc", "-O2", main_c, "-o", rg])
            gen_c = os.path.join(B, "gen_table.c")
            open(gen_c, "w").write(f"/* generated at build time by {cid} {version}. output, not "
                                   f"source: do not edit */\n" + sh([rg]))
            build.gen_table_o = os.path.join(B, "gen_table.o")
            sh(["gcc", "-O2", "-fPIC", "-c", gen_c, "-o", build.gen_table_o])
            open(os.path.join(cdir(cid), "gen_table.c"), "w").write(open(gen_c).read())
        elif linkage == "internal":
            o = obj(cid, sym, true_spdx, version)
            static_a[cid] = archive(cid, [o])
            ic = os.path.join(B, "ingest.c")
            open(ic, "w").write(f"int {sym}_fn(int);\nint main(void){{return {sym}_fn(1)&1;}}\n")
            oi = os.path.join(B, "ingest.o"); sh(["gcc", "-O2", "-c", ic, "-o", oi])
            sh(["gcc", "-O2", "-o", os.path.join(prod, "tools", "ingest"), oi, static_a[cid]])
        elif linkage == "chain":
            # MIT wrapper archive that bundles a vendored GPL-2.0 object; both reach the binary
            d = cdir(cid)
            tp = os.path.join(d, "third_party", "gpl-core")
            os.makedirs(tp, exist_ok=True)
            open(os.path.join(tp, "LICENSE"), "w").write(LICENSE_TEXT["GPL-2.0-only"])
            gc = os.path.join(tp, "gpl_core.c")
            open(gc, "w").write(spdx_header("GPL-2.0-only") +
                                "int gplcore_mix(int x){return (int)(((unsigned)x*2654435761u)&0x7fffffff);}\n")
            wc = write_src(cid, sym, true_spdx, version)
            # rewrite wrapper to call the vendored gpl symbol
            open(wc, "w").write(spdx_header(true_spdx) + f"/* version {version} */\n"
                                "int gplcore_mix(int);\n"
                                f"int {sym}_fn(int x){{ return gplcore_mix(x) ^ 0x55; }}\n")
            ogc = os.path.join(B, "gplcore.o"); owc = os.path.join(B, "chwrap.o")
            sh(["gcc", "-O2", "-fPIC", "-c", gc, "-o", ogc])
            sh(["gcc", "-O2", "-fPIC", "-c", wc, "-o", owc])
            static_a[cid] = archive(cid, [owc, ogc])
            collector_static.append(static_a[cid]); collector_calls.append(sym)

    # ---- reporter
    decls = "".join(f"int {s}_fn(int);\n" for s in reporter_calls)
    calls = " + ".join(f"{s}_fn({i+1})" for i, s in enumerate(reporter_calls)) or "0"
    dlo = ""
    for i, (cid, pname, sym) in enumerate(reporter_dlopen):
        dlo += (f'  {{ void*h=dlopen("plugins/{pname}",RTLD_NOW); if(h){{'
                f'int(*f)(int)=(int(*)(int))dlsym(h,"{sym}_fn"); if(f) a+=f({i+3});}} }}\n')
    reporter_c = os.path.join(B, "reporter.c")
    open(reporter_c, "w").write(
        "/* SPDX-License-Identifier: LicenseRef-Proprietary */\n#include <stdio.h>\n#include <dlfcn.h>\n"
        + decls + "extern const int gen_table[8];\nint main(void){\n"
        f"  int a = {calls} + gen_table[3];\n" + dlo +
        '  printf("reporter %d\\n", a);\n  return 0;\n}\n')
    o_rep = os.path.join(B, "reporter.o"); sh(["gcc", "-O2", "-c", reporter_c, "-o", o_rep])
    link = ["gcc", "-O2", "-o", os.path.join(prod, "bin", "reporter"), o_rep, build.gen_table_o] \
        + reporter_static + ["-L" + os.path.join(prod, "lib")] \
        + [f"-l:{n}" for n in reporter_dyn] + ["-Wl,-rpath," + os.path.join(prod, "lib"), "-ldl"]
    sh(link)

    # ---- collector
    decls = "".join(f"int {s}_fn(int);\n" for s in collector_calls)
    calls = " + ".join(f"{s}_fn({i+1})" for i, s in enumerate(collector_calls)) or "0"
    collector_c = os.path.join(B, "collector.c")
    open(collector_c, "w").write(
        "/* SPDX-License-Identifier: LicenseRef-Proprietary */\n#include <stdio.h>\n#include <unistd.h>\n"
        "#include <sys/wait.h>\n" + decls + "int main(void){\n"
        f"  int a = {calls};\n"
        '  pid_t p = fork(); if(p==0){ execl("tools/imgtool","imgtool",(char*)0); _exit(127);} '
        'int st; if(p>0) waitpid(p,&st,0);\n'
        '  printf("collector %d\\n", a);\n  return 0;\n}\n')
    o_col = os.path.join(B, "collector.o"); sh(["gcc", "-O2", "-c", collector_c, "-o", o_col])
    sh(["gcc", "-O2", "-o", os.path.join(prod, "bin", "collector"), o_col] + collector_static)

    sh(["rm", "-rf", B])


def emit_docs(root):
    open(os.path.join(root, "POLICY.md"), "w").write(POLICY_MD)
    open(os.path.join(root, "BUILD.md"), "w").write(BUILD_MD)
    open(os.path.join(root, "RELEASE.txt"), "w").write(
        f"product: cfs-collector-suite\nrelease: 7.4.0\nship_date: {SHIP_DATE}\n")

    # SBOM: administrative tracking only. the license column is wrong for csvlite/xmlmini and the
    # version column is misstated for polymath (reads in-range, but the source version is not). it
    # does NOT record how anything is linked -- that is only in the artifacts.
    SBOM_VERSION = {"polymath": "1.5"}
    rows = [("component_id", "sbom_license", "version")]
    for (cid, sbom_spdx, _t, _s, _target, _linkage, version, _g, _p, _d) in COMPONENTS:
        rows.append((cid, sbom_spdx, SBOM_VERSION.get(cid, version)))
    with open(os.path.join(root, "sbom.tsv"), "w") as fh:
        for r in rows:
            fh.write("\t".join(r) + "\n")

    # procurement register: catalog maps proc-id -> component; grants give scope + expiry
    proc = os.path.join(root, "procurement")
    os.makedirs(proc, exist_ok=True)
    cat = [("procurement_id", "component_id")]
    grn = [("procurement_id", "covers_version_range", "expires_on")]
    for (cid, *_r, grant, _p, _d) in COMPONENTS:
        if grant:
            pid, rng, exp = grant
            cat.append((pid, cid))
            grn.append((pid, rng, exp))
    # a decoy grant that names a component which is not copyleft
    cat.append(("PROC-20", "flatjson")); grn.append(("PROC-20", ">=1.0 <2.0", "2027-01-01"))
    with open(os.path.join(proc, "catalog.csv"), "w") as fh:
        for r in cat:
            fh.write(",".join(r) + "\n")
    with open(os.path.join(proc, "grants.csv"), "w") as fh:
        for r in grn:
            fh.write(",".join(r) + "\n")

    # published corresponding source register: component -> published_version
    pubrows = [("component_id", "published_version")]
    for (cid, *_r, _g, pub, _d) in COMPONENTS:
        if pub:
            pubrows.append((cid, pub))
    with open(os.path.join(root, "published_source.csv"), "w") as fh:
        for r in pubrows:
            fh.write(",".join(r) + "\n")


POLICY_MD = """\
# CFS-DIST-4  distribution policy (standing)

this is our policy, not a ruling on any one component, and it is not the fsf's rules. read it as
what legal has actually signed off for this product. it does not decide any single component.

## what we ship

customers get a tarball of `product/` and nothing else. the delivered binaries are
`product/bin/reporter`, `product/bin/collector`, the shared objects under `product/lib` they load
and the plugins under `product/plugins` they open. `product/tools` is operational, we run it in
house and it is not in the tarball, and neither is anything used only to build.

a component is part of the delivered work when its own machine code is inside a delivered file
(its symbols are present there), however it got in, or when we ship it and a delivered binary
loads it at run time. a component we only run as a separate program in its own process is not part
of the delivered work.

generated output is ours, not the generator's. when a tool we run at build time writes a table or
a source file that we then compile into a delivered binary, the symbols that output defines belong
to our build, not to the tool's component. they do not carry the tool's license and they do not
make the tool part of the delivered work. the one exception is a tool that copies its own code into
what it writes (a parser skeleton, an embedded runtime). that copied code is the tool's and counts
under the rule above.

## the license of record is not the governing license

`sbom.tsv` carries a license of record for tracking. it is administrative and it is not authority.
the governing license for a component is the spdx identifier in that component's own source and
license files, and where the two differ the source wins. decide on the source. the version
column is kept the same way: the version we ship is the version stated in the component's own
source, not the one on record. a component can carry code under more than one license, for
example source it vendored with its own license file beside it, and each part is governed by its
own license wherever that part ends up.

## how a copyleft obligation gets met here

for a component that is part of the delivered work and carries a copyleft license (any gpl, agpl
or lgpl), the obligation is met, and the component is fine to ship, in exactly these ways and no
others:

- lgpl, where the delivered binary links it as a shared library the customer could replace. a
  weak copyleft library statically bound into a binary we never let anyone relink is not met this
  way.
- a live commercial grant. `procurement/catalog.csv` says which grant covers which component and
  `procurement/grants.csv` gives each grant's version range and the date it expires. a grant meets
  the obligation only when it names the component, the version we ship falls inside its range, and
  its term has not expired as of the ship date in `RELEASE.txt`.
- we publish the complete corresponding source. `published_source.csv` lists the components whose
  source we publish and the version we published. this meets the obligation only when the version
  we publish is the version we ship. source for an older version is not corresponding source.

anything else that is copyleft and part of the delivered work is not something we can ship.
permissive licenses, a file level copyleft on files we did not modify, a license offered to us as
a choice where one option is permissive, and a copyleft license carrying a linking exception are
all fine and are not findings.

## the finding

write the components that are part of the delivered work and carry a copyleft obligation we have
not met by one of the routes above. a component that is fine the way we ship it is not a finding,
whatever its license, and a component that is not part of the delivered work is not a finding.
"""

BUILD_MD = """\
# the product build (file map for the audit)

`product/` is the release tree: `product/bin` has the two delivered binaries, `product/lib` and
`product/plugins` hold shared objects and plugins, `product/tools` is operational tooling.
`components/<id>` has each component's license and source. `sbom.tsv`, `procurement/catalog.csv`,
`procurement/grants.csv` and `published_source.csv` are our records, and `RELEASE.txt` has the
ship date. POLICY.md says which of these count as delivered.

every component is built from its source exactly as it sits in `components/<id>`. we carry no
local patches against any third party code.
"""


def main():
    out_app, out_ans = sys.argv[1], sys.argv[2]
    sh(["rm", "-rf", out_app]); os.makedirs(out_app, exist_ok=True)
    build(out_app)
    emit_docs(out_app)
    os.makedirs(os.path.dirname(out_ans) or ".", exist_ok=True)
    all_ids = sorted(c[0] for c in COMPONENTS)
    json.dump({"disqualifying": ANSWER, "components": all_ids}, open(out_ans, "w"), indent=2)
    print("components:", len(COMPONENTS), " disqualifying:", len(ANSWER), ANSWER)


if __name__ == "__main__":
    main()
