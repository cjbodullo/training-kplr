#!/usr/bin/env python3
"""Measure a bundle against every other bundle in task-src before submitting.

    python3 kepler-tools/simscan.py <slug> [--top 8]

Three numbers, because the gate has blocked on each of them at least once:

  prose    TF-IDF cosine over instruction.md word unigrams+bigrams
  gram     character 4-gram Jaccard over instruction.md
  shape    Jaccard over the bundle manifest (top-level dirs, dir names,
           file basenames, file stems) - this is the one that blocked
           pass-mark v1 against credit-fold
"""
import argparse
import collections
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "task-src")
SKIP_DIRS = {"dev", "jobs", "__pycache__", ".git", "cheat", "spike",
             "authoring", ".pytest_cache"}


def words(text):
    t = re.findall(r"[a-z0-9_/.]+", text.lower())
    return t + [f"{a}_{b}" for a, b in zip(t, t[1:])]


def grams(text, n=4):
    t = re.sub(r"\s+", " ", text.lower())
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def manifest(slug):
    """Structural names only.  A directory holding bulk generated data counts
    once, as a bulk directory, or 700 uniquely named run files swamp the set
    and every bundle looks distinct from every other one."""
    base = os.path.join(SRC, slug)
    out = set()
    for dirpath, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and not d.startswith("jobs")]
        rel = os.path.relpath(dirpath, base)
        if rel != ".":
            parts = rel.split(os.sep)
            out.add("dir:" + parts[0])
            out.add("dirname:" + parts[-1])
        keep = [f for f in files if not f.endswith((".pyc", ".zip", ".log"))]
        if len(keep) > 15:
            out.add("bulk:" + os.path.basename(dirpath))
            out.add("bulkext:" + os.path.splitext(keep[0])[1])
            continue
        for f in keep:
            out.add("file:" + f)
            out.add("stem:" + os.path.splitext(f)[0])
    return out


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a or b) else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()

    slugs, texts = [], {}
    for s in sorted(os.listdir(SRC)):
        p = os.path.join(SRC, s, "instruction.md")
        if os.path.isfile(p):
            slugs.append(s)
            texts[s] = open(p, errors="ignore").read()
    if a.slug not in texts:
        sys.exit(f"no instruction.md for {a.slug}")

    # tf-idf over the whole local corpus
    docs = {s: collections.Counter(words(t)) for s, t in texts.items()}
    df = collections.Counter()
    for c in docs.values():
        df.update(c.keys())
    N = len(docs)
    vecs = {}
    for s, c in docs.items():
        v = {w: (1 + math.log(n)) * math.log(N / (1 + df[w]))
             for w, n in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs[s] = {w: x / norm for w, x in v.items()}

    me_v, me_g, me_m = vecs[a.slug], grams(texts[a.slug]), manifest(a.slug)

    rows = []
    for s in slugs:
        if s == a.slug:
            continue
        other = vecs[s]
        small, big = (me_v, other) if len(me_v) < len(other) else (other, me_v)
        cos = sum(x * big.get(w, 0.0) for w, x in small.items())
        rows.append((s, cos, jaccard(me_g, grams(texts[s])),
                     jaccard(me_m, manifest(s))))

    print(f"{a.slug} against {len(rows)} local bundles\n")
    for label, key in (("prose  tf-idf cosine", 1), ("gram   4-gram jaccard", 2),
                       ("shape  manifest jaccard", 3)):
        top = sorted(rows, key=lambda r: -r[key])[:a.top]
        print(f"-- {label}   max {top[0][key]:.3f}")
        for r in top:
            print(f"   {r[0]:<24} prose {r[1]:.3f}  gram {r[2]:.3f}  "
                  f"shape {r[3]:.3f}")
        print()

    worst = max(rows, key=lambda r: max(r[1], r[2], r[3]))
    print(f"nearest overall: {worst[0]} "
          f"(prose {worst[1]:.3f}, gram {worst[2]:.3f}, shape {worst[3]:.3f})")


if __name__ == "__main__":
    main()
