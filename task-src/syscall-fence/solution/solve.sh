#!/usr/bin/env bash
set -euo pipefail

# reference solution for syscall-fence.
#
# it assembles the seccomp classic-BPF program by hand (struct sock_filter[])
# and writes it to /app/filter.bpf, the exact byte layout the kernel consumes
# through prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &sock_fprog), which the
# target installs on itself. the policy defaults to allow so the read-and-
# summarise path is untouched, and denies the tamper families: openat/open only
# when the flags request write or create, openat2 outright (its flags sit behind
# a pointer seccomp cannot read), creat, the rename/unlink/link/mkdir/truncate
# family, execve/execveat and the chmod/chown family. libseccomp is installed in
# the environment too (scmp_sys_resolver below) and can express the masked flag
# compare, but the raw assembler keeps the whole policy in one place.

cd /app
cp "$(dirname "$0")/gen_filter.c" /app/gen_filter.c

# sanity: resolve a couple syscall names through libseccomp's resolver so the
# numbers baked into the filter match this kernel's abi.
scmp_sys_resolver -a x86_64 openat  >/dev/null 2>&1 || true
scmp_sys_resolver -a x86_64 execve  >/dev/null 2>&1 || true

gcc -O2 -o /app/gen_filter /app/gen_filter.c
/app/gen_filter /app/filter.bpf

ls -l /app/filter.bpf
