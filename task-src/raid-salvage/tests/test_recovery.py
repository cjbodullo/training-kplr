"""grade the tarn salvage: /app/out/recovered.tar and /app/out/lost.txt against the
sealed state of the share at the moment the array died (/tests/truth.json).

every regular file of that filesystem must be in exactly one of the two outputs.
files in the tar must be byte exact. lost.txt must name exactly the files with at
least one byte that the four member images cannot determine.
"""
import hashlib
import json
import posixpath
import tarfile

import pytest

TAR = "/app/out/recovered.tar"
LOST = "/app/out/lost.txt"

with open("/tests/truth.json") as fh:
    TRUTH = json.load(fh)
FILES = TRUTH["files"]
LOST_TRUE = set(TRUTH["lost"])


def norm(name):
    p = posixpath.normpath("/" + name.strip())
    if p.startswith("//"):
        p = p[1:]
    return p


def read_tar():
    got, problems = {}, []
    with tarfile.open(TAR, "r:*") as t:
        members = t.getmembers()
        for m in members:
            p = norm(m.name)
            if ".." in m.name.split("/"):
                problems.append(f"path escapes root: {m.name!r}")
                continue
            if m.isdir():
                continue
            if not (m.isreg() or m.islnk()):
                problems.append(f"not a regular file: {m.name!r}")
                continue
            if p in got:
                problems.append(f"duplicate entry: {p}")
                continue
            f = t.extractfile(m)
            if f is None:
                problems.append(f"unreadable entry: {p}")
                continue
            got[p] = hashlib.sha256(f.read()).hexdigest()
    return got, problems


def read_lost():
    with open(LOST, "rb") as fh:
        raw = fh.read().decode("utf-8")
    out, dups = set(), []
    for line in raw.split("\n"):
        line = line.rstrip("\r")
        if not line.strip():
            continue
        p = norm(line)
        if p in out:
            dups.append(p)
        out.add(p)
    return out, dups


@pytest.fixture(scope="module")
def tar_contents():
    return read_tar()


@pytest.fixture(scope="module")
def lost_list():
    return read_lost()


def test_tar_is_clean(tar_contents):
    _got, problems = tar_contents
    assert not problems, problems[:10]


def test_lost_list_is_clean(lost_list):
    _lost, dups = lost_list
    assert not dups, dups[:10]


def test_no_paths_outside_filesystem(tar_contents, lost_list):
    got, _ = tar_contents
    lost, _ = lost_list
    extra = sorted((set(got) | lost) - set(FILES))
    assert not extra, f"{len(extra)} paths that are not regular files of the share: {extra[:10]}"


def test_every_file_accounted_for_once(tar_contents, lost_list):
    got, _ = tar_contents
    lost, _ = lost_list
    both = sorted(set(got) & lost)
    assert not both, f"in the tar and in lost.txt: {both[:10]}"
    missing = sorted(set(FILES) - set(got) - lost)
    assert not missing, f"{len(missing)} files in neither output: {missing[:10]}"


def test_no_undeterminable_file_handed_back(tar_contents):
    got, _ = tar_contents
    given = sorted(set(got) & LOST_TRUE)
    assert not given, f"{len(given)} files handed back that the images cannot determine"


def test_no_recoverable_file_written_off(lost_list):
    lost, _ = lost_list
    wrong = sorted(lost & (set(FILES) - LOST_TRUE))
    assert not wrong, f"{len(wrong)} recoverable files listed as lost: {wrong[:10]}"


def test_lost_list_complete(lost_list):
    lost, _ = lost_list
    missed = sorted(LOST_TRUE - lost)
    assert not missed, f"{len(missed)} undeterminable files missing from lost.txt"


def test_recovered_bytes_exact(tar_contents):
    got, _ = tar_contents
    bad = sorted(p for p, h in got.items() if p in FILES and h != FILES[p]["sha256"])
    assert not bad, f"{len(bad)} files with wrong content: {bad[:10]}"
