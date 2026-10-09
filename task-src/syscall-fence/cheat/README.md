cheat attempts for syscall-fence (never executed by harbor; here for the author).

the task cannot be passed by a syscall-number denylist, which is the obvious move.

1. partial_filter.c -- default allow, deny tamper syscalls by number, treating
   openat as one thing. two ways it fails, both caught by the verifier:
     - deny openat outright: the benign jobs can no longer read their data files,
       so they do not print the right summary and those tests fail.
     - allow openat: the openat-with-write-flags tamper creates its file, so that
       tamper test fails.
   it also omits family members (openat2, creat, renameat2, unlinkat, fchmodat,
   execveat, symlinkat, ...), each of which is a separate syscall number; any one
   left out lets that tamper through.

2. a "default allow, block nothing" filter (or no file at all) passes every
   benign job but fails all eleven tamper checks.

the only passing filter reads the target's real behaviour: allow openat only when
the flags are read-only (mask O_WRONLY|O_RDWR|O_CREAT), deny openat2 outright
because its flags sit behind a pointer seccomp cannot read, and cover every member
of the write/delete/rename/link/mkdir/exec/chmod families. the grader loads the
filter into the real kernel via the target and checks real filesystem effects, so
no self-reported success is trusted.
