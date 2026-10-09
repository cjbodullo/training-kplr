#!/usr/bin/env python3
"""anchor_check.py — real-world tool anchoring scan for a kepler bundle source dir.

The rule (CLAUDE.md, "Real-world tool anchoring"): every task must be anchored in named,
real software that exists outside the bundle. Name it in instruction.md, install it in
environment/, drive it in solution/, grade its real output in tests/.

This is an advisory scan, not a pipeline gate. It catches the mechanical half of the rule:
tools named but never installed, tools installed but never named, generic placeholder
phrasing, and version strings that drifted between instruction.md and the Dockerfile.
The judgement half ("does the anchor carry weight") stays with kepler-idea step 1b.

usage:
    python3 kepler-tools/anchor_check.py task-src/<slug>
    python3 kepler-tools/anchor_check.py task-src/<slug> --tools freecad,numpy
    python3 kepler-tools/anchor_check.py task-src/<slug> --tools bun --strict

exit: 0 clean (or warnings only), 1 errors found (or warnings with --strict).
"""

import argparse
import pathlib
import re
import sys

# phrasing that stands where a real tool name belongs. matched case-insensitively on
# instruction.md prose. each is a warning with a line number, never an automatic fail —
# some are legitimate in context ("the tool exits nonzero" right after naming it).
GENERIC_PHRASES = [
    r"\ba (?:small |simple |custom |bespoke |little )?(?:program|script|tool|binary|utility)\b",
    r"\bthe (?:program|software|tool|binary|utility|framework|library|engine)\b",
    r"\b(?:a|the) (?:custom|bespoke|toy|mock|fake|in.?house) \w+",
    r"\b(?:a|the) simulator\b",
    r"\bsome (?:program|tool|software|library)\b",
    r"\bthis (?:program|tool|software)\b",
]

# how tools get installed. group 1 (or the named group) is the package/image spec.
INSTALL_PATTERNS = [
    (r"apt-get\s+install(?:\s+-\w+|\s+--[\w-]+)*\s+([^\n&|]+)", "apt"),
    (r"(?:pip3?|uv pip)\s+install(?:\s+-\w+|\s+--[\w-]+)*\s+([^\n&|]+)", "pip"),
    (r"npm\s+(?:install|i)(?:\s+-\w+|\s+--[\w-]+)*\s+([^\n&|]+)", "npm"),
    (r"cargo\s+install\s+([^\n&|]+)", "cargo"),
    (r"opam\s+install(?:\s+-\w+|\s+--[\w-]+)*\s+([^\n&|]+)", "opam"),
    (r"^\s*FROM\s+(\S+)", "image"),
    (r"^\s*image:\s*[\"']?([^\"'\s]+)", "image"),
]

# package tokens that are plumbing, not the anchor. reported separately so the signal
# is not buried under build-essential and ca-certificates.
PLUMBING = {
    "build-essential", "ca-certificates", "curl", "wget", "git", "gnupg", "unzip",
    "xz-utils", "tar", "make", "cmake", "gcc", "g++", "pkg-config", "software-properties-common",
    "apt-transport-https", "libssl-dev", "procps", "bash", "coreutils", "locales", "tzdata",
    "python3-pip", "python3-venv", "python3-dev", "setuptools", "wheel", "pip",
    "less", "vim", "nano", "ripgrep", "jq", "file", "findutils", "rsync", "ssh", "openssh-client",
    # generic base images — a version pin on these is plumbing, not an anchor. a base image
    # that IS the anchor (postgres:16, node:22) is deliberately absent from this set.
    "python", "debian", "ubuntu", "alpine", "busybox", "scratch",
}

VERSION_RE = re.compile(r"(?:==|@|:)\s*(\d+(?:\.\d+)+[\w.\-]*)")


def read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def strip_code(text: str) -> str:
    """drop fenced blocks so prose scanning does not trip over sample code."""
    return re.sub(r"```.*?```", "", text, flags=re.S)


def collect_installs(bundle: pathlib.Path):
    """-> (packages, versions) across environment/ build files.

    packages maps name -> install kind. versions maps name -> pinned version, and only
    carries anchor packages: a pin on a plumbing base image is not an anchor version.
    """
    packages, versions = {}, {}
    sources = [
        bundle / "environment" / "Dockerfile",
        bundle / "environment" / "docker-compose.yaml",
        bundle / "environment" / "docker-compose.yml",
    ]
    # sidecar images built from sub-directories (compose `build:` contexts) carry anchors too
    sources += sorted(p for p in (bundle / "environment").rglob("Dockerfile") if p.parent != bundle / "environment")
    for src in sources:
        if not src.is_file():
            continue
        text = read(src)
        # unwrap line continuations so multi-line apt installs read as one line
        text = text.replace("\\\n", " ")
        for pattern, kind in INSTALL_PATTERNS:
            for m in re.finditer(pattern, text, flags=re.M):
                for token in m.group(1).split():
                    if token.startswith("-") or token in {"&&", "\\"}:
                        continue
                    name = re.split(r"[=@:<>\[]", token, maxsplit=1)[0].strip().lower()
                    name = name.rsplit("/", 1)[-1]  # docker.io/library/postgres -> postgres
                    if not name or name in PLUMBING:
                        continue
                    packages.setdefault(name, kind)
                    found = VERSION_RE.findall(token)
                    if found:
                        versions.setdefault(name, found[0])
        # rustup installs a toolchain (rust, rustc, cargo) plus named components
        for m in re.finditer(r"--default-toolchain\s+(\S+)", text):
            for name in ("rust", "rustc", "cargo"):
                packages.setdefault(name, "rustup")
                versions.setdefault(name, m.group(1))
        for m in re.finditer(r"--component\s+([\w,\-]+)", text):
            for name in m.group(1).split(","):
                packages.setdefault(name.lower(), "rustup")
    return packages, versions


def scan_generic(instruction: str):
    hits = []
    for lineno, line in enumerate(strip_code(instruction).splitlines(), 1):
        for pattern in GENERIC_PHRASES:
            for m in re.finditer(pattern, line, flags=re.I):
                hits.append((lineno, m.group(0).strip()))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="real-world tool anchoring scan")
    ap.add_argument("bundle", help="bundle source dir, e.g. task-src/<slug>")
    ap.add_argument("--tools", default="",
                    help="comma separated tool names the task claims to be anchored in")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failure")
    args = ap.parse_args()

    bundle = pathlib.Path(args.bundle).resolve()
    if not bundle.is_dir():
        print(f"error: not a directory: {bundle}")
        return 1

    instruction_path = bundle / "instruction.md"
    if not instruction_path.is_file():
        print(f"error: no instruction.md in {bundle}")
        return 1

    instruction = read(instruction_path)
    instruction_lc = instruction.lower()
    solution = "".join(read(p) for p in (bundle / "solution").rglob("*") if p.is_file())
    tests = "".join(read(p) for p in (bundle / "tests").rglob("*") if p.is_file())
    packages, versions = collect_installs(bundle)

    errors, warnings = [], []
    print(f"anchor scan: {bundle.name}")

    # 1. declared tools must be named in the instruction AND installed in the environment
    declared = [t.strip().lower() for t in args.tools.split(",") if t.strip()]
    if declared:
        print("\ndeclared tools")
        for tool in declared:
            named = tool in instruction_lc
            installed = any(tool in pkg or pkg in tool for pkg in packages)
            driven = tool in solution.lower()
            graded = tool in tests.lower()
            marks = "".join([
                "N" if named else "-", "E" if installed else "-",
                "S" if driven else "-", "T" if graded else "-",
            ])
            print(f"  [{marks}] {tool}")
            # Being named in instruction.md is a WARNING per tool, not an error. The
            # AfterQuery quality check penalises an instruction that enumerates the
            # installed toolchain ("the agent should discover it"), so demanding every
            # tool by name would trade one rejection for another. What the anchoring
            # rule actually needs is that the instruction is not generic — enforced in
            # aggregate below — and that the tools are really installed and driven.
            if not named:
                warnings.append(f"{tool}: not named in instruction.md")
            if not installed:
                errors.append(f"{tool}: no install found in environment/")
            if not driven:
                warnings.append(f"{tool}: solution/ never invokes it — is the anchor decoration?")

        if not any(t in instruction_lc for t in declared):
            errors.append(
                "instruction.md names NONE of the declared tools, and no real artifact "
                "stands in for them — the instruction reads as unanchored")
        print("  legend: N=named in instruction  E=installed in environment  "
              "S=driven by solution  T=used by tests")

    # 2. what the environment installs that the instruction never mentions
    unnamed = sorted(p for p in packages if p not in instruction_lc)
    if packages:
        print("\ninstalled in environment/")
        for pkg in sorted(packages):
            flag = " " if pkg in instruction_lc else "?"
            print(f"  {flag} {pkg} ({packages[pkg]})")
        if unnamed:
            warnings.append(
                "installed but never named in instruction.md: " + ", ".join(unnamed[:12]))
    else:
        warnings.append("no tool installs detected in environment/ — is this task anchored at all?")

    # 3. version drift between the Dockerfile and the instruction
    if versions:
        print("\nversions pinned in environment/")
        for name in sorted(versions):
            print(f"  {name} {versions[name]}")
        drifted = sorted(f"{n}=={v}" for n, v in versions.items() if v not in instruction)
        if drifted:
            warnings.append(
                "pinned versions absent from instruction.md: " + ", ".join(drifted[:12]))

    # 4. generic placeholder phrasing
    hits = scan_generic(instruction)
    if hits:
        print("\ngeneric phrasing in instruction.md")
        for lineno, phrase in hits[:20]:
            print(f"  line {lineno}: \"{phrase}\"")
        if len(hits) > 20:
            print(f"  ... and {len(hits) - 20} more")
        warnings.append(f"{len(hits)} generic phrase(s) where a real tool name may belong")

    print()
    for e in errors:
        print(f"ERROR   {e}")
    for w in warnings:
        print(f"warning {w}")
    if not errors and not warnings:
        print("clean.")

    print("\nthis scan is mechanical. the judgement call stays yours: would swapping the named "
          "tool\nfor a stub change the difficulty? if not, the anchor is decoration "
          "(kepler-idea step 1b).")

    if errors:
        return 1
    return 1 if (warnings and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
