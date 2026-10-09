#!/usr/bin/env python3
"""Find the nearest neighbours of a bundle in my own catalogue.

    python3 kepler-tools/prescreen/twin.py task-src/<slug> [--top 12]

The similarity gate is semantic and it names nothing, so this is a stand in:
tf-idf over word unigrams and bigrams, cosine, run over three views of every
bundle — the instruction, the task.toml prose, and the two together.  A high
score against a bundle that is LIVE in the index is a candidate twin.

difflib character ratios are useless here (everything lands near 0.06); word
level tf-idf is much closer to what an embedding model keys on.
"""
import argparse
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "task-src")

STOP = set("""a an the and or but if then than that this these those of in on at to for
with from by as is are was were be been being it its i we you they he she them us our
your their not no so do does did done have has had will would can could should may might
must about into over under out up down off again once here there when where why how all
any both each few more most other some such only own same too very s t just now""".split())


def words(text):
    text = text.lower()
    text = re.sub(r"`[^`]*`", " ", text)          # drop code spans
    text = re.sub(r"[^a-z ]+", " ", text)
    toks = [w for w in text.split() if len(w) > 2 and w not in STOP]
    return toks + ["%s_%s" % (a, b) for a, b in zip(toks, toks[1:])]


def read(slug, view):
    out = []
    if view in ("instruction", "both"):
        p = os.path.join(SRC, slug, "instruction.md")
        if os.path.exists(p):
            out.append(open(p, encoding="utf-8", errors="replace").read())
    if view in ("toml", "both"):
        p = os.path.join(SRC, slug, "task.toml")
        if os.path.exists(p):
            t = open(p, encoding="utf-8", errors="replace").read()
            out.append(" ".join(re.findall(r'"""(.*?)"""', t, re.S)))
    return "\n".join(out)


def vectors(slugs, view):
    docs = {s: words(read(s, view)) for s in slugs}
    docs = {s: d for s, d in docs.items() if d}
    df = {}
    for d in docs.values():
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    n = len(docs)
    vecs = {}
    for s, d in docs.items():
        tf = {}
        for w in d:
            tf[w] = tf.get(w, 0) + 1
        v = {w: (1 + math.log(c)) * math.log(n / df[w]) for w, c in tf.items()
             if df[w] < n * 0.6}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs[s] = {w: x / norm for w, x in v.items()}
    return vecs


def cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    me = os.path.basename(os.path.normpath(args.bundle))

    slugs = sorted(d for d in os.listdir(SRC)
                   if os.path.isdir(os.path.join(SRC, d)))
    if me not in slugs:
        print("%s is not under task-src" % me)
        return 2

    for view in ("instruction", "toml", "both"):
        vecs = vectors(slugs, view)
        if me not in vecs:
            continue
        scored = sorted(((cosine(vecs[me], vecs[s]), s) for s in vecs
                         if s != me), reverse=True)
        print("\n== %s ==" % view)
        for sc, s in scored[:args.top]:
            print("   %.3f  %s" % (sc, s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
