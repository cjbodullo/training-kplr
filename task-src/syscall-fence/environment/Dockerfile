FROM debian:bookworm-slim

# toolchain for building and loading a seccomp classic-BPF program:
#   gcc + libc headers to assemble the struct sock_filter[] program,
#   libseccomp (the standard userspace library for seccomp filters) and its
#   headers + resolver, plus strace to observe the target's syscalls.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        libseccomp-dev \
        seccomp \
        strace \
        python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# build the target the agent must sandbox, ship it stripped (source is not left
# in the image), and give the agent sample jobs + data to run it with.
COPY data/target.c /tmp/target.c
RUN gcc -O2 -o /app/target /tmp/target.c && strip /app/target && rm -f /tmp/target.c
RUN mkdir -p /app/samples /app/out
COPY data/sample1.job data/sample2.job /app/samples/
COPY data/data_a.txt data/data_b.txt data/data_c.txt /app/samples/
