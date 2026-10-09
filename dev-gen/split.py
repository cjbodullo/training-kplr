"""Split generated cases into the visible backlog (environment) and the sealed set (tests).

  python3 dev-gen/split.py --out dev-gen/out2 --visible 400 --heldout 200 --seed 7

Cases are renamed to fresh ids so nothing about the generator's seed ordering leaks.
Prints feature coverage for both splits and refuses a split where a feature present in
the held-out set is absent from the visible set.
"""

import argparse
import glob
import json
import os
import random
import shutil

TASK = "/root/work/anand_kepler/task-src/copybook-record-decoder"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--visible", type=int, default=400)
    ap.add_argument("--heldout", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-visible", type=int, default=6, help="min visible cases per feature seen in held-out")
    args = ap.parse_args()
    results = {}
    for p in sorted(glob.glob(os.path.join(args.out, "results-*.json"))):
        for k, v in json.load(open(p)).items():
            if v.get("ok") or k not in results:
                results[k] = v
    ok = sorted(k for k, v in results.items() if v.get("ok") and os.path.isdir(os.path.join(args.out, "cases", k)))
    print("usable cases:", len(ok))
    need = args.visible + args.heldout
    if len(ok) < need:
        raise SystemExit("need %d cases, have %d" % (need, len(ok)))
    rng = random.Random(args.seed)
    rng.shuffle(ok)
    chosen = ok[:need]
    for attempt in range(200):
        rng.shuffle(chosen)
        vis, held = chosen[:args.visible], chosen[args.visible:]
        fv, fh = {}, {}
        for k in vis:
            for f in results[k]["features"]:
                fv[f] = fv.get(f, 0) + 1
        for k in held:
            for f in results[k]["features"]:
                fh[f] = fh.get(f, 0) + 1
        bad = [f for f in fh if fv.get(f, 0) < args.min_visible]
        if not bad:
            break
        print("attempt %d: under-covered in visible: %s" % (attempt, bad))
    else:
        raise SystemExit("could not find a covering split")
    print("%-24s %8s %8s" % ("feature", "visible", "heldout"))
    for f in sorted(set(fv) | set(fh)):
        print("%-24s %8d %8d" % (f, fv.get(f, 0), fh.get(f, 0)))
    vdir = os.path.join(TASK, "environment", "data", "app", "cases")
    hdir = os.path.join(TASK, "tests", "cases")
    for d in (vdir, hdir):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    ids = ["c%04d" % i for i in range(1, need + 1)]
    rng.shuffle(ids)
    mapping = {}
    for src_id, new_id in zip(vis + held, ids):
        dst_root = vdir if src_id in set(vis) else hdir
        src = os.path.join(args.out, "cases", src_id)
        dst = os.path.join(dst_root, new_id)
        shutil.copytree(src, dst)
        meta = json.load(open(os.path.join(dst, "case.json")))
        meta["id"] = new_id
        with open(os.path.join(dst, "case.json"), "w") as fh_:
            json.dump(meta, fh_, indent=1)
            fh_.write("\n")
        mapping[new_id] = src_id
    with open(os.path.join(args.out, "id-map.json"), "w") as fh_:
        json.dump(mapping, fh_, indent=1)
    print("visible:", len(os.listdir(vdir)), "held-out:", len(os.listdir(hdir)))


if __name__ == "__main__":
    main()
