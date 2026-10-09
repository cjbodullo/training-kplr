#!/usr/bin/env python3
"""
Rebuild hook for an ai_check failure: humanize instruction.md, then verify the
must-stay-exact tokens survived (the humanizer scrambles protected placeholders),
and only if clean rebuild the bundle zip.

Usage:
    python3 rebuild_aicheck.py --src <task-src-dir> --zip <out.zip> [--require tokens.txt]

Exit codes:
    0  humanized + integrity clean + zip rebuilt
    2  integrity failed (tokens scrambled/missing) — did NOT touch the zip; fix by hand
    1  other error

IMPORTANT: the humanizer can silently invert meaning ("committed after" -> "before").
This checks token PRESENCE and the exact suffix, not semantics. Always eyeball the
diff on an ai_check auto-rebuild before trusting it.
"""

import argparse
import sys
import re
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kepler-instruction"))
import humanize as H  # noqa: E402
from bundle import build_zip  # noqa: E402


def expected_suffix(src):
    toml = tomllib.loads((Path(src) / "task.toml").read_text())
    n = int(toml["agent"]["timeout_sec"])
    return f"You have {n} seconds to complete this task. Do not cheat by using online solutions or hints specific to this task."


def integrity(text, src, required):
    problems = []
    suffix = expected_suffix(src)
    if suffix not in text:
        problems.append(f"required suffix missing/altered (expected: {suffix!r})")
    for tok in required:
        if tok and tok not in text:
            problems.append(f"required token missing: {tok!r}")
    # known scramble tells seen from the humanizer
    for bad in ["raises `None`", "throw `abort`", "rewrite `Database` in place", "return `read(key)`"]:
        if bad in text:
            problems.append(f"scramble detected: {bad!r}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--zip", required=True)
    ap.add_argument("--require", default=None)
    ap.add_argument("--dry-run", action="store_true", help="humanize + check, do not write files")
    args = ap.parse_args()

    src = Path(args.src)
    ins = src / "instruction.md"
    original = ins.read_text()

    required = []
    req_file = args.require or (src / "required_tokens.txt")
    if Path(req_file).exists():
        required = [l.strip() for l in Path(req_file).read_text().splitlines() if l.strip()]

    print(f"humanizing {ins} ...")
    r = H.humanize(original, keep_last_line=True)
    humanized = r["humanized"]
    print(f"  scores: {r['scores']}")

    problems = integrity(humanized, src, required)
    if problems:
        print("INTEGRITY FAILED — not rebuilding the zip. fix by hand:")
        for p in problems:
            print(f"  - {p}")
        # write a review copy so a human/agent can correct it
        review = src / "instruction.humanized.review.md"
        review.write_text(humanized)
        print(f"  humanized draft written for correction: {review}")
        sys.exit(2)

    print("integrity clean.")
    if args.dry_run:
        print("dry-run: not writing.")
        return
    ins.write_text(humanized)
    out = build_zip(str(src), args.zip)
    print(f"rebuilt bundle: {out}")


if __name__ == "__main__":
    main()
