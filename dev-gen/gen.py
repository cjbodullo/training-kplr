"""Corpus driver. Runs INSIDE the gnucobol container:

  docker run --rm -v $PWD/dev-gen:/g -v $PWD/task-src/copybook-record-decoder/solution:/sol \
      -v <out>:/out cobexp python3 /g/gen.py --start 0 --count 480 --out /out

For each seed it builds a case, compiles and runs the writer with cobc, decodes the data
with the reference decoder and compares against the expected records. Cases that fail to
compile, run, or agree are reported and skipped (never shipped).
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/sol")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ast_gen import build_case, assign_record, expected_json, inherit, approx_size   # noqa: E402
from emit import Style, Emitter, emit_writer                             # noqa: E402
from unpack.decode import decode_case                                    # noqa: E402


def case_options(rng):
    opts = {}
    opts["line_seq"] = rng.random() < 0.14
    opts["ebcdic"] = (not opts["line_seq"]) and rng.random() < 0.22
    opts["multi01"] = rng.random() < 0.16
    opts["odo"] = (not opts["multi01"]) and rng.random() < 0.22
    opts["copy"] = rng.random() < 0.22
    opts["init"] = "low" if (not opts["line_seq"] and rng.random() < 0.15) else "space"
    opts["record_clause"] = rng.random() < 0.18 and not opts["line_seq"]
    opts["n_records"] = rng.randint(24, 60)
    return opts


def make_case(seed, out_dir, case_id):
    rng = random.Random(seed * 7919 + 17)
    opts = case_options(rng)
    ctx = build_case(seed, opts)
    ctx.opts = opts
    style = Style(ctx.rng)
    if opts["line_seq"]:
        # sanity: line sequential needs an all-DISPLAY layout
        for L in ctx.records:
            for it in L.walk():
                if not it.children and it.eff_usage != "DISPLAY":
                    raise RuntimeError("non-display item under line sequential")
    em = Emitter(ctx, style)
    lines = em.emit_copybook(ctx.records)
    cpy_name = rng.choice(["layout.cpy", "%s.cpy" % ctx.prefix, "%sREC.cpy" % ctx.prefix, "record.cpy", "%s.CPY" % ctx.prefix.lower()])
    # exact record sizes (with SYNC padding) from the reference layout of the emitted text
    import tempfile
    from unpack.copybook import parse_copybook
    from unpack.layout import Layout
    with tempfile.TemporaryDirectory() as _td:
        with open(os.path.join(_td, cpy_name), "w", encoding="latin-1") as fh:
            fh.write("\n".join(lines) + "\n")
        for fname, sub in em.files.items():
            with open(os.path.join(_td, fname), "w", encoding="latin-1") as fh:
                fh.write("\n".join(sub) + "\n")
        exact_max = Layout(parse_copybook(os.path.join(_td, cpy_name))).max_size
    meta = {"id": case_id, "copybook": cpy_name, "data": "data.dat"}
    meta["organization"] = "LINE SEQUENTIAL" if opts["line_seq"] else "SEQUENTIAL"
    fd = []
    special = []
    if opts["record_clause"]:
        r = rng.random()
        if r < 0.3:
            fd.append("RECORD IS VARYING IN SIZE DEPENDING ON WS-LEN")
            ctx.f("record-varying-dep")
        elif r < 0.45:
            fd.append("RECORD IS VARYING IN SIZE")
            ctx.f("record-varying")
        elif r < 0.75:
            mx = exact_max
            lo = rng.randint(1, max(1, mx - 1))
            fd.append("RECORD IS VARYING IN SIZE FROM %d TO %d CHARACTERS" % (lo, mx) if rng.random() < 0.5
                      else "RECORD VARYING FROM %d TO %d DEPENDING ON WS-LEN" % (lo, mx))
            ctx.f("record-from-to")
        else:
            mx = exact_max
            fd.append("RECORD CONTAINS %d CHARACTERS" % mx)
            ctx.f("record-contains")
    if opts["ebcdic"]:
        aname = rng.choice(["EBCDIC-SET", "EBC", "MF-CODESET", "IBM-ALPHA"])
        special.append("ALPHABET %s IS EBCDIC" % aname)
        fd.append("CODE-SET IS %s" % aname)
        ctx.f("ebcdic")
    if opts["line_seq"]:
        ctx.f("line-seq")
    meta["fd"] = fd
    meta["special_names"] = special
    if ctx.layouts:
        disc, mp, default, offkey = ctx.layouts
        meta["layouts"] = {"discriminator": disc.name,
                           "map": {k: L.name for k, L in mp.items()},
                           "default": default.name if default is not None else None}
    if ctx.variants:
        meta["variants"] = []
        for orig, disc, mp, default, offkey in ctx.variants:
            meta["variants"].append({"of": orig.name, "discriminator": disc.name,
                                     "map": {k: a.name for k, a in mp.items()},
                                     "default": default.name if default is not None else None})
    # values
    recs = [assign_record(ctx, i) for i in range(opts["n_records"])]
    expected = [expected_json(ctx, r) for r in recs]
    # write files
    cdir = os.path.join(out_dir, "cases", case_id)
    wdir = os.path.join(out_dir, "work", case_id)
    for d in (cdir, wdir):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    with open(os.path.join(cdir, cpy_name), "w", encoding="latin-1") as fh:
        fh.write("\n".join(lines) + "\n")
    for fname, sub in em.files.items():
        with open(os.path.join(cdir, fname), "w", encoding="latin-1") as fh:
            fh.write("\n".join(sub) + "\n")
    with open(os.path.join(cdir, "case.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
        fh.write("\n")
    with open(os.path.join(cdir, "expected.jsonl"), "w", encoding="utf-8") as fh:
        for e in expected:
            fh.write(json.dumps(e, ensure_ascii=True) + "\n")
    src = emit_writer(ctx, recs, meta)
    with open(os.path.join(wdir, "writer.cob"), "w", encoding="latin-1") as fh:
        fh.write(src)
    # compile + run in the case dir (copybooks resolve there)
    env = dict(os.environ)
    env["COB_COPY_DIR"] = cdir
    p = subprocess.run(["cobc", "-x", "-I", cdir, "-o", os.path.join(wdir, "writer"), os.path.join(wdir, "writer.cob")],
                       capture_output=True, text=True, cwd=cdir, env=env)
    if p.returncode != 0:
        return {"ok": False, "stage": "compile", "msg": (p.stderr + p.stdout)[-3000:], "features": sorted(ctx.features)}
    p = subprocess.run([os.path.join(wdir, "writer")], capture_output=True, text=True, cwd=cdir, timeout=120)
    if p.returncode != 0 or not os.path.exists(os.path.join(cdir, "data.dat")):
        return {"ok": False, "stage": "run", "msg": (p.stderr + p.stdout)[-3000:], "features": sorted(ctx.features)}
    # decode with the reference and compare
    try:
        got = list(decode_case(os.path.join(cdir, "case.json")))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "stage": "decode", "msg": repr(e)[:3000], "features": sorted(ctx.features)}
    if got != expected:
        msg = diff_summary(expected, got)
        return {"ok": False, "stage": "compare", "msg": msg, "features": sorted(ctx.features)}
    return {"ok": True, "features": sorted(ctx.features), "records": len(expected),
            "bytes": os.path.getsize(os.path.join(cdir, "data.dat")), "copybook": cpy_name}


def diff_summary(exp, got):
    if len(exp) != len(got):
        return "record count expected %d got %d" % (len(exp), len(got))
    for i, (e, g) in enumerate(zip(exp, got)):
        if e != g:
            path = first_diff(e, g)
            return "record %d: %s" % (i, path)
    return "?"


def first_diff(e, g, path="$"):
    if isinstance(e, dict) and isinstance(g, dict):
        for k in e:
            if k not in g:
                return "%s.%s missing in decoded" % (path, k)
            if e[k] != g[k]:
                return first_diff(e[k], g[k], path + "." + k)
        for k in g:
            if k not in e:
                return "%s.%s extra in decoded" % (path, k)
        return path + " ?"
    if isinstance(e, list) and isinstance(g, list):
        if len(e) != len(g):
            return "%s length expected %d got %d" % (path, len(e), len(g))
        for i, (a, b) in enumerate(zip(e, g)):
            if a != b:
                return first_diff(a, b, "%s[%d]" % (path, i))
        return path + " ?"
    return "%s expected %r got %r" % (path, e, g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="c")
    ap.add_argument("--keep-failed", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    results = {}
    t0 = time.time()
    for seed in range(args.start, args.start + args.count):
        cid = "%s%04d" % (args.prefix, seed)
        try:
            r = make_case(seed, args.out, cid)
        except Exception as e:  # noqa: BLE001
            import traceback
            r = {"ok": False, "stage": "gen", "msg": traceback.format_exc()[-3000:]}
        results[cid] = r
        flag = "ok " if r["ok"] else "FAIL[%s]" % r["stage"]
        print("%s %s %s" % (cid, flag, r.get("msg", "")[:300].replace("\n", " | ") if not r["ok"] else "%d rec %d B" % (r["records"], r["bytes"])), flush=True)
        if not r["ok"] and not args.keep_failed:
            cdir = os.path.join(args.out, "cases", cid)
            if os.path.isdir(cdir):
                shutil.rmtree(cdir)
    with open(os.path.join(args.out, "results-%d-%d.json" % (args.start, args.count)), "w") as fh:
        json.dump(results, fh, indent=1)
    ok = sum(1 for r in results.values() if r["ok"])
    print("done %d/%d ok in %.0fs" % (ok, len(results), time.time() - t0))


if __name__ == "__main__":
    main()
