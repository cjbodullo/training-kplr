# syscall-fence — submission sheet

## category & labels
- **category:** Security  (matches `[metadata].category`)
- **label (subcategory):** AppSec  (`[metadata].subcategory = "AppSec"`)

## task name
`syscall-fence`  (matches `[task].name = "afterquery/syscall-fence"`)

## author
Shaswat Panda / pandashaswat712@gmail.com (from credentials.md)

## bundle zip
`tasks/syscall-fence/syscall-fence.zip` — built with
`python3 kepler-tools/bundle.py task-src/syscall-fence tasks/syscall-fence/syscall-fence.zip`.

## what the task is (redesigned)
The agent is given a compiled, stripped program `/app/target` that reads a job file, does
read-and-summarise work, and on some inputs tries to tamper with the machine (create/write
files, delete/rename/link, mkdir, exec, chmod). The agent must deliver a raw `struct sock_filter[]`
seccomp program at `/app/filter.bpf`; the target installs it on itself (NO_NEW_PRIVS +
SECCOMP_MODE_FILTER) at startup, so it governs everything the job then does. The filter must stop
every tamper's effect while keeping the read-and-summarise path working on all inputs.

The difficulty is reverse-engineering + a seccomp fact, not transcription: seccomp sees syscall
numbers and scalar args, never the path strings behind pointers. Benign reads and malicious writes
both go through `openat`, so it must be split on the open flags (deny O_WRONLY/O_RDWR/O_CREAT,
allow O_RDONLY, mask so O_CLOEXEC isn't mistaken for a write). `openat2` can't be split (flags
behind a pointer) so it must be denied outright. And the tamper surface is whole families
(creat, rename/renameat/renameat2, unlink/unlinkat, link/symlink families, mkdir/mkdirat,
execve/execveat, chmod/fchmod/fchmodat/chown family) — miss one member and that tamper leaks;
over-block the read side and the summary breaks.

## verifier shape
`tests/target.c` (sealed; stripped copy shipped to the agent) self-installs the agent's filter and
runs sealed job files. `tests/test_fence.py` runs the target under 4 benign jobs (must exit 0 +
exact summary) and 11 tamper jobs (effect must be absent: no secret-bearing file, guard file
survives rename/unlink and keeps mode 0644, no dir/symlink, exec helper's exit-code-42 signal
never surfaces). Reward 1 iff all pass. The agent supplies only filter bytes; the grader runs its
own sealed target.

## local gates (all green)
- anchor scan: clean (seccomp [NEST], strace [NE--]).
- `harbor run -a oracle` on the **extracted zip**: reward **1.000**.
- `harbor run -a nop` on the **extracted zip**: reward **0.000**.
- `metadata_check`: clean. No instruction headings. Suffix N=18000 == agent budget.
- Discrimination verified locally: a filter that blocks `openat` wholesale fails the benign jobs;
  one that only handles `openat` (missing creat/openat2/rename/unlink/symlink/mkdir/chmod/exec)
  leaks those tampers; default-allow/no-filter fails all 11 tamper checks. See `cheat/`.

## fix history
- v1–v3 (spelled-out syscall→action table) failed quality `difficult` as "transcription".
  Redesigned so difficulty is reverse-engineering a real binary + seccomp path-blindness.
- Fixed a zip-packaging bug: the job dir was named `tests/jobs/`, which `bundle.py` strips
  (jobs* prefix = harbor output); renamed to `tests/cases/`. Re-validated on the extracted zip.

## note for review
The local `harbor check` only runs the structural criteria subset, not the server-side rubric that
raised `difficult`; that gate is only observable on resubmit. Difficulty not screened with a live
agent locally (no API key for the difficulty probe).
