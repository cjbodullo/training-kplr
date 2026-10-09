FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends xz-utils && rm -rf /var/lib/apt/lists/*

# etcd 3.5.17 release binaries, plus etcd-dump-logs and etcd-dump-db built from the v3.5.17 tag
COPY data/etcd-v3.5.17-linux-amd64.tar.gz data/etcd-tools-v3.5.17.tar.xz /tmp/
RUN tar -xzf /tmp/etcd-v3.5.17-linux-amd64.tar.gz -C /tmp \
    && install -m 0755 /tmp/etcd-v3.5.17-linux-amd64/etcd /tmp/etcd-v3.5.17-linux-amd64/etcdctl /tmp/etcd-v3.5.17-linux-amd64/etcdutl /usr/local/bin/ \
    && tar -xJf /tmp/etcd-tools-v3.5.17.tar.xz -C /usr/local/bin \
    && rm -rf /tmp/etcd-v3.5.17-linux-amd64* /tmp/etcd-tools-v3.5.17.tar.xz

# what survived of tarn-kv: the m4 and m5 data dirs as found on disk, and the services' call logs
COPY data/tarn-kv.tar.xz /tmp/
RUN mkdir -p /data && tar -xJf /tmp/tarn-kv.tar.xz -C /data && rm /tmp/tarn-kv.tar.xz

RUN mkdir -p /app/out
WORKDIR /app
