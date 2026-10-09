#!/usr/bin/env python3
"""Shared bundle zip builder. Zips the CONTENTS of a task source dir (no wrapping
folder) into a deliverable zip, excluding non-bundle files."""

import os
import zipfile

# source-only files that must never ship in the deliverable (some contain the
# blocked provenance terms afterquery/kepler and would fail the structure check).
EXCLUDE_NAMES = {"SUBMISSION.md", "required_tokens.txt", "last_failure.md",
                 "failures.log", "submit_loop.log", "poll_until_done.py",
                 "SPIKE.md"}
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "dev",
                "spike", "authoring"}
# harbor job output lands in jobs/, jobs2/, gates/, ... none of it belongs in a bundle
EXCLUDE_DIR_PREFIX = ("jobs",)
EXCLUDE_SUFFIX = (".pyc", ".zip", ".log", ".bin", ".rpt")
# EPANET/wntr scratch files land in the cwd of whatever ran a simulation
EXCLUDE_NAMES |= {"temp.inp", "temp.bin", "temp.rpt"}


# the structure check rejects these outright. task.toml is exempt for
# "afterquery" only, because [task].name must be afterquery/<slug>.
BLOCKED_TERMS = ("kepler", "afterquery", "anvil")


def _blocked_hits(path, rel):
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return []
    # decode('utf-8', 'ignore') DROPS invalid bytes rather than replacing them, so it splices
    # characters that are not adjacent in the file. In tens of megabytes of compressed data a
    # short word turns up that way by chance (measured: one 'anvil' in a 56 MB zstd parquet,
    # sitting in high entropy noise, with b'anvil' appearing nowhere in the bytes). A term
    # counts only if it is really there: present in the raw bytes, or in a clean decode.
    lowered = data.lower()
    text = data.decode("utf-8", "ignore").lower()
    hits = []
    for term in BLOCKED_TERMS:
        raw_hit = term.encode() in lowered
        if not raw_hit and term not in text:
            continue
        if not raw_hit:
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                continue          # binary file, spliced word, not actually present
        if term == "afterquery" and rel == "task.toml":
            continue
        hits.append(term)
    return hits


def check_artifact_parents(src):
    """The one static check no local gate reproduces.

    The remote structure check pattern-matches tests/Dockerfile TEXT for a
    standalone `RUN mkdir -p <parent>` for every declared artifact. A chained
    mkdir, or the line sitting in environment/Dockerfile instead, both build a
    perfectly good image and both are rejected. Costs a validation slot AND a
    similarity round, because the rejected record becomes a predecessor ghost.
    """
    toml_path = os.path.join(src, "task.toml")
    dockerfile = os.path.join(src, "tests", "Dockerfile")
    if not (os.path.exists(toml_path) and os.path.exists(dockerfile)):
        return []
    try:
        import tomllib
        with open(toml_path, "rb") as fh:
            artifacts = tomllib.load(fh).get("artifacts") or []
    except Exception:
        return []
    with open(dockerfile, encoding="utf-8", errors="ignore") as fh:
        lines = [ln.strip() for ln in fh]

    missing = []
    for art in artifacts:
        if isinstance(art, dict):  # { source = ..., service = ... } entries
            art = art.get("source", "")
        parent = os.path.dirname(art) or "/"
        standalone = any(
            ln.startswith("RUN mkdir -p ") and parent in ln.split()[3:]
            for ln in lines if ln.startswith("RUN mkdir -p "))
        if not standalone:
            missing.append(parent)
    return missing


def build_zip(src, out):
    src = os.path.abspath(src)
    out = os.path.abspath(out)
    missing = check_artifact_parents(src)
    if missing:
        raise SystemExit(
            "refusing to write %s: tests/Dockerfile has no standalone "
            "`RUN mkdir -p` for the parent of every declared artifact, and the "
            "remote structure check rejects that (artifact-parent-not-created).\n"
            "Add to tests/Dockerfile, each on its own line:\n%s"
            % (out, "\n".join("  RUN mkdir -p %s" % p for p in sorted(set(missing)))))
    found = {}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS
                       and not d.startswith(EXCLUDE_DIR_PREFIX)]
            for fn in sorted(files):
                if fn in EXCLUDE_NAMES or fn.endswith(EXCLUDE_SUFFIX):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, src)
                hits = _blocked_hits(full, rel)
                if hits:
                    found[rel] = hits
                z.write(full, rel)
    if found:
        os.remove(out)
        raise SystemExit(
            "refusing to write %s: blocked provenance terms would ship and the "
            "structure check rejects them.\n%s"
            % (out, "\n".join("  %s -> %s" % (r, ", ".join(t))
                              for r, t in sorted(found.items()))))
    return out


if __name__ == "__main__":
    import sys
    print("wrote", build_zip(sys.argv[1], sys.argv[2]))
