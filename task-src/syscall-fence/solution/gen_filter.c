/* reference filter generator for syscall-fence.
 *
 * emits the raw struct sock_filter[] seccomp program to argv[1] (default
 * /app/filter.bpf). the policy keeps the target's normal read-and-summarise
 * work (default allow) but neutralises every tamper path:
 *   - file creation / writing: openat and open are allowed only when the flags
 *     are read-only (O_WRONLY/O_RDWR/O_CREAT all rejected with EACCES); creat
 *     is rejected; openat2 is rejected outright, because its flags live behind a
 *     pointer that seccomp cannot inspect.
 *   - delete / rename / link / mkdir: the whole family is rejected.
 *   - exec: execve and execveat are rejected.
 *   - permission / ownership change: chmod/fchmod/fchmodat/chown family rejected.
 * everything else falls through to allow, so the summary path is untouched.
 *
 * built with a small two-pass label assembler so jump offsets are computed.
 */
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <linux/seccomp.h>
#include <linux/filter.h>
#include <sys/syscall.h>

#define MAXI 512
#define OFF_NR 0
#define OFF_ARG_LO(i) (16u + 8u*(i))
#define A_ALLOW 0x7fff0000u
#define A_ERRNO(e) (0x00050000u | ((e) & 0xffff))

/* open flags that mean "this call can create or write a file" */
#define WRITE_OPEN_MASK (01 /*O_WRONLY*/ | 02 /*O_RDWR*/ | 0100 /*O_CREAT*/)

#ifndef SYS_openat2
#define SYS_openat2 437
#endif
#ifndef SYS_renameat2
#define SYS_renameat2 316
#endif
#ifndef SYS_execveat
#define SYS_execveat 322
#endif

enum { L_ALLOW, L_DENY, NLABEL };
static struct sock_filter ins[MAXI];
static int n = 0;
static struct { int idx, field, label; } fix[MAXI*2];
static int nfix = 0;
static int label_at[NLABEL];

static void emit(struct sock_filter f){ ins[n++] = f; }
static int jmp(int field, int label){ fix[nfix].idx=n; fix[nfix].field=field; fix[nfix].label=label; return nfix++; }
static void place(int l){ label_at[l]=n; }

int main(int argc, char **argv){
    const char *path = argc > 1 ? argv[1] : "/app/filter.bpf";

    emit((struct sock_filter)BPF_STMT(BPF_LD|BPF_W|BPF_ABS, OFF_NR));

    /* openat / open: jump into a flags handler when matched, else fall through */
    int j_openat = nfix; jmp(0, -1); emit((struct sock_filter)BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, SYS_openat, 0, 0));
    int j_open   = nfix; jmp(0, -1); emit((struct sock_filter)BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, SYS_open,   0, 0));

    /* deny-outright family: match -> jump to the EACCES return, else fall through */
    int deny[] = {
        SYS_openat2, SYS_creat,
        SYS_rename, SYS_renameat, SYS_renameat2,
        SYS_unlink, SYS_unlinkat,
        SYS_link, SYS_linkat, SYS_symlink, SYS_symlinkat,
        SYS_mkdir, SYS_mkdirat, SYS_rmdir, SYS_mknod, SYS_mknodat,
        SYS_truncate, SYS_ftruncate,
        SYS_execve, SYS_execveat,
        SYS_chmod, SYS_fchmod, SYS_fchmodat,
        SYS_chown, SYS_fchown, SYS_lchown, SYS_fchownat,
    };
    for (unsigned i = 0; i < sizeof(deny)/sizeof(deny[0]); i++){
        jmp(0, L_DENY);
        emit((struct sock_filter)BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K, deny[i], 0, 0));
    }

    /* default: allow (fall-through from the last deny JEQ) */
    emit((struct sock_filter)BPF_STMT(BPF_RET|BPF_K, A_ALLOW));

    /* openat handler: deny when any write/create bit is set, else allow */
    int h_openat = n;
    emit((struct sock_filter)BPF_STMT(BPF_LD|BPF_W|BPF_ABS, OFF_ARG_LO(2)));
    jmp(0, L_DENY);                 /* JSET mask: set -> DENY */
    jmp(1, L_ALLOW);                /*            clear -> ALLOW */
    emit((struct sock_filter)BPF_JUMP(BPF_JMP|BPF_JSET|BPF_K, WRITE_OPEN_MASK, 0, 0));

    /* open handler: same flags check (arg2 is flags for open too) */
    int h_open = n;
    emit((struct sock_filter)BPF_STMT(BPF_LD|BPF_W|BPF_ABS, OFF_ARG_LO(1)));  /* open: flags = arg1 */
    jmp(0, L_DENY);
    jmp(1, L_ALLOW);
    emit((struct sock_filter)BPF_JUMP(BPF_JMP|BPF_JSET|BPF_K, WRITE_OPEN_MASK, 0, 0));

    place(L_ALLOW); emit((struct sock_filter)BPF_STMT(BPF_RET|BPF_K, A_ALLOW));
    place(L_DENY);  emit((struct sock_filter)BPF_STMT(BPF_RET|BPF_K, A_ERRNO(EACCES)));

    /* point the openat/open dispatch jumps at their handlers */
    fix[j_openat].label = -1000 - h_openat;
    fix[j_open  ].label = -1000 - h_open;

    for (int q = 0; q < nfix; q++){
        int tgt;
        if (fix[q].label <= -1000) tgt = -1000 - fix[q].label;
        else if (fix[q].label < 0) continue;
        else tgt = label_at[fix[q].label];
        int off = tgt - fix[q].idx - 1;
        if (off < 0){ fprintf(stderr, "backward jump at %d\n", fix[q].idx); return 3; }
        if (off > 255){ fprintf(stderr, "jump too far at %d (%d)\n", fix[q].idx, off); return 3; }
        if (fix[q].field == 0) ins[fix[q].idx].jt = (unsigned char)off;
        else                   ins[fix[q].idx].jf = (unsigned char)off;
    }

    FILE *fp = fopen(path, "wb");
    if (!fp){ perror("fopen"); return 2; }
    if (fwrite(ins, sizeof(struct sock_filter), n, fp) != (size_t)n){ perror("fwrite"); return 2; }
    fclose(fp);
    fprintf(stderr, "wrote %d instructions to %s\n", n, path);
    return 0;
}
