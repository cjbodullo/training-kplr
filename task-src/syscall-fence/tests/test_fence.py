"""sealed grader for syscall-fence.

the agent delivers /app/filter.bpf (raw struct sock_filter[]). the target program
(/tests/target, sealed) installs that filter on itself at startup and then runs a
job. we run the target under several sealed jobs and grade:

  * benign jobs must still finish (exit 0) and print the exact summary -- this
    forces the filter not to break the read-and-summarise path.
  * tamper jobs must have NO effect on the filesystem -- the created/written file
    must not appear, the guard file must survive rename/unlink and keep its mode,
    the directory/symlink must not appear, the exec marker must not appear.

for tamper jobs we check only the effect, so the filter may reject with an errno
or kill the process; either way the effect must be absent. the agent supplies only
filter bytes; the grader runs its own sealed target, never agent code.
"""
import os
import stat
import shutil
import subprocess

import pytest

TARGET = "/tests/target"
JOBS = "/tests/cases"
FILTER = "/app/filter.bpf"
OUT = "/app/out"
GUARD = "/app/guard"

# sums are fixed by the sealed data files: a=60, b=10, c=95
BENIGN = {
    "b1.job": "sum=70 files=2",
    "b2.job": "sum=60 files=1",
    "b3.job": "sum=95 files=1",
    "b4.job": "sum=165 files=3",
}


def reset_scratch():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    with open(GUARD, "w") as f:
        f.write("guard-contents\n")
    os.chmod(GUARD, 0o644)


def run(job):
    return subprocess.run([TARGET, os.path.join(JOBS, job)],
                          capture_output=True, text=True, timeout=60)


def leaked(path):
    """a write tamper 'worked' if the file exists and holds the secret bytes."""
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            return "SECRET" in f.read()
    except OSError:
        return False


def test_filter_present():
    assert os.path.isfile(FILTER), "/app/filter.bpf not found"
    sz = os.path.getsize(FILTER)
    assert sz > 0 and sz % 8 == 0, "filter empty or not whole sock_filter records"


def test_filter_loads():
    reset_scratch()
    r = run("b1.job")
    assert r.returncode == 0, f"target failed to run under the filter: rc={r.returncode} err={r.stderr!r}"


@pytest.mark.parametrize("job,expected", sorted(BENIGN.items()))
def test_benign_still_works(job, expected):
    reset_scratch()
    r = run(job)
    assert r.returncode == 0, f"{job}: exit {r.returncode}, stderr={r.stderr!r}"
    assert r.stdout.strip() == expected, f"{job}: stdout={r.stdout!r} expected {expected!r}"


def test_tamper_openat_write():
    reset_scratch(); run("m_wopen.job")
    assert not leaked(f"{OUT}/leak1")


def test_tamper_creat():
    reset_scratch(); run("m_creat.job")
    assert not leaked(f"{OUT}/leak2")


def test_tamper_openat2():
    reset_scratch(); run("m_openat2.job")
    assert not leaked(f"{OUT}/leak3")


def test_tamper_rename():
    reset_scratch(); run("m_rename.job")
    assert os.path.exists(GUARD), "guard was renamed away"
    assert not os.path.exists(f"{OUT}/moved")


def test_tamper_unlink():
    reset_scratch(); run("m_unlink.job")
    assert os.path.exists(GUARD), "guard was unlinked"


def test_tamper_symlink():
    reset_scratch(); run("m_symlink.job")
    assert not os.path.lexists(f"{OUT}/sl")


def test_tamper_mkdir():
    reset_scratch(); run("m_mkdir.job")
    assert not os.path.exists(f"{OUT}/d")


def test_tamper_exec():
    # the helper signals it ran via exit code 42, which survives any filter, so
    # the only way to pass is to block execve itself (filters persist across exec).
    reset_scratch(); r = run("m_exec.job")
    assert r.returncode != 42, "execve was not blocked (helper ran)"


def test_tamper_execveat():
    reset_scratch(); r = run("m_execveat.job")
    assert r.returncode != 42, "execveat was not blocked (helper ran)"


def test_tamper_chmod():
    reset_scratch(); run("m_chmod.job")
    assert stat.S_IMODE(os.stat(GUARD).st_mode) == 0o644, "guard mode changed"


def test_tamper_fchmodat():
    reset_scratch(); run("m_fchmodat.job")
    assert stat.S_IMODE(os.stat(GUARD).st_mode) == 0o644, "guard mode changed"
