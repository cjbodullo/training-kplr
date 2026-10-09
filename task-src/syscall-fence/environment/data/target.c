/* target.c -- the program the agent must sandbox.
 *
 * it reads a job file (argv[1]); each line is one directive. it installs the
 * seccomp filter at /app/filter.bpf on ITSELF (NO_NEW_PRIVS + SECCOMP_MODE_FILTER)
 * right after reading the filter and before running any directive, so everything
 * the directives do is governed by the agent's filter. the dynamic loader and the
 * filter load itself run before the filter is active.
 *
 * benign directives read data files and print a summary to stdout. some inputs
 * carry a tamper directive (write/create/delete/rename/link/mkdir/exec/chmod);
 * the agent's filter must stop those from having any effect while the summary
 * path keeps working.
 *
 * this file is sealed in the verifier. a stripped build is shipped to the agent
 * as /app/target for them to run and reverse engineer.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <linux/seccomp.h>
#include <linux/filter.h>

#ifndef SYS_openat2
#define SYS_openat2 437
#endif
#ifndef SYS_execveat
#define SYS_execveat 322
#endif

struct open_how { uint64_t flags, mode, resolve; };

static struct sock_filter prog[8192];

static void install_filter(void){
    int fd = open("/app/filter.bpf", O_RDONLY | O_CLOEXEC);
    if (fd < 0) return;                       /* no filter -> run unsandboxed */
    long n = read(fd, prog, sizeof(prog));
    close(fd);
    if (n <= 0 || (n % (long)sizeof(struct sock_filter))) return;
    struct sock_fprog fp = { .len = (unsigned short)(n / sizeof(struct sock_filter)),
                             .filter = prog };
    prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0);
    prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &fp);
}

/* benign: read a file of whitespace-separated integers and add them up.
 * uses openat(O_RDONLY|O_CLOEXEC), newfstatat, read, close. */
static long long read_sum(const char *path, int *ok){
    *ok = 0;
    struct stat st;
    syscall(SYS_newfstatat, AT_FDCWD, path, &st, 0);      /* stat first */
    long fd = syscall(SYS_openat, AT_FDCWD, path, O_RDONLY | O_CLOEXEC, 0);
    if (fd < 0) return 0;
    static char buf[1 << 16];
    long long total = 0; long r; long long cur = 0; int in = 0, neg = 0;
    while ((r = syscall(SYS_read, fd, buf, sizeof(buf))) > 0){
        for (long i = 0; i < r; i++){
            char c = buf[i];
            if (c == '-' && !in){ neg = 1; in = 1; cur = 0; }
            else if (c >= '0' && c <= '9'){ in = 1; cur = cur * 10 + (c - '0'); }
            else { if (in){ total += neg ? -cur : cur; } in = 0; neg = 0; cur = 0; }
        }
    }
    if (in) total += neg ? -cur : cur;
    syscall(SYS_close, fd);
    *ok = 1;
    return total;
}

static void do_big(void){
    void *p = (void *)syscall(SYS_mmap, 0, 4L << 20, PROT_READ | PROT_WRITE,
                              MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p != MAP_FAILED){ memset(p, 1, 4096); syscall(SYS_munmap, p, 4L << 20); }
}
static void do_nonce(void){ char b[16]; syscall(SYS_getrandom, b, sizeof(b), 0); }
static void do_time(void){ struct { long s, ns; } t; syscall(SYS_clock_gettime, 1, &t); }

int main(int argc, char **argv){
    if (argc < 2){ fprintf(stderr, "usage: target <job>\n"); return 2; }

    /* read the whole job file before installing the filter is not required, but
     * the filter must be installed before any directive runs. */
    FILE *job = fopen(argv[1], "r");
    if (!job){ fprintf(stderr, "no job\n"); return 2; }
    static char lines[4096][512];
    int nl = 0;
    while (nl < 4096 && fgets(lines[nl], sizeof(lines[0]), job)) nl++;
    fclose(job);

    install_filter();

    long long total = 0; int files = 0;
    for (int i = 0; i < nl; i++){
        char *ln = lines[i];
        char *nlp = strchr(ln, '\n'); if (nlp) *nlp = 0;
        if (!ln[0] || ln[0] == '#') continue;
        char a[512] = {0}, b[512] = {0}, c[512] = {0};
        char op[64] = {0};
        sscanf(ln, "%63s %511s %511s %511s", op, a, b, c);

        if (!strcmp(op, "read")){ int ok; total += read_sum(a, &ok); if (ok) files++; }
        else if (!strcmp(op, "big"))   do_big();
        else if (!strcmp(op, "nonce")) do_nonce();
        else if (!strcmp(op, "time"))  do_time();
        /* ---- tamper directives: the filter must neutralise these ---- */
        else if (!strcmp(op, "wopen")){
            long fd = syscall(SYS_openat, AT_FDCWD, a,
                              O_WRONLY | O_CREAT | O_TRUNC, 0644);
            if (fd >= 0){ syscall(SYS_write, fd, "SECRET\n", 7); syscall(SYS_close, fd); }
        }
        else if (!strcmp(op, "creat")){
            long fd = syscall(SYS_creat, a, 0644);
            if (fd >= 0){ syscall(SYS_write, fd, "SECRET\n", 7); syscall(SYS_close, fd); }
        }
        else if (!strcmp(op, "openat2")){
            struct open_how how = { .flags = O_WRONLY | O_CREAT | O_TRUNC, .mode = 0644 };
            long fd = syscall(SYS_openat2, AT_FDCWD, a, &how, sizeof(how));
            if (fd >= 0){ syscall(SYS_write, fd, "SECRET\n", 7); syscall(SYS_close, fd); }
        }
        else if (!strcmp(op, "rename"))   syscall(SYS_rename, a, b);
        else if (!strcmp(op, "unlink"))   syscall(SYS_unlink, a);
        else if (!strcmp(op, "symlink"))  syscall(SYS_symlink, a, b);
        else if (!strcmp(op, "mkdir"))    syscall(SYS_mkdir, a, 0755);
        else if (!strcmp(op, "exec")){
            char *av[] = { a, NULL }; char *ev[] = { NULL };
            syscall(SYS_execve, a, av, ev);
        }
        else if (!strcmp(op, "execveat")){
            char *av[] = { a, NULL }; char *ev[] = { NULL };
            syscall(SYS_execveat, AT_FDCWD, a, av, ev, 0);
        }
        else if (!strcmp(op, "chmod"))    syscall(SYS_chmod, a, 0777);
        else if (!strcmp(op, "fchmodat")) syscall(SYS_fchmodat, AT_FDCWD, a, 0777, 0);
    }

    printf("sum=%lld files=%d\n", total, files);
    return 0;
}
