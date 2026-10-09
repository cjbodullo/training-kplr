/* helper for the exec tamper vector. seccomp filters persist across execve, so a
 * filter that blocks file writes would also stop a helper that writes a marker
 * file -- that would let the exec vector pass without blocking execve itself.
 * instead this signals "i ran" purely by its exit code, which survives any
 * filter, so the only way to stop it is to block execve/execveat. */
int main(void){ return 42; }
