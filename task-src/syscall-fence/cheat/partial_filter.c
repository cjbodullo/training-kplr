/* cheat attempt: the "obvious" seccomp filter -- default allow, then block the
 * tamper syscalls by NUMBER only. it handles execve/chmod/unlink/... but it
 * treats openat as a single thing: either it allows openat (then the write/create
 * tamper via openat leaks) or it denies openat (then the benign reads break). it
 * also forgets that openat2/creat/renameat2 are separate numbers. so it cannot
 * pass: the verifier's benign jobs break or a tamper family member gets through.
 * the only passing filter splits openat on its flags, denies openat2 outright,
 * and covers every family member -- which needs reverse engineering the target,
 * not a syscall list. */
#include <stdio.h>
#include <linux/seccomp.h>
#include <linux/filter.h>
#include <sys/syscall.h>
#include <errno.h>
#define ALLOW 0x7fff0000u
#define DENY (0x00050000u|(EACCES&0xffff))
int main(int argc,char**argv){
  /* block openat ENTIRELY (and a few families) -> benign reads break */
  struct sock_filter f[]={
    BPF_STMT(BPF_LD|BPF_W|BPF_ABS,0),
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_openat,3,0),
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_execve,2,0),
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_unlink,1,0),
    BPF_STMT(BPF_RET|BPF_K,ALLOW),
    BPF_STMT(BPF_RET|BPF_K,DENY),
  };
  FILE*fp=fopen(argc>1?argv[1]:"/app/filter.bpf","wb");
  fwrite(f,8,sizeof(f)/8,fp); fclose(fp); return 0;
}
