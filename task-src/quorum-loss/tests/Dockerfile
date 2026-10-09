FROM python:3.13-slim-bookworm

# everything the verifier needs is installed here; test.sh never installs anything
RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2

# bake the tests, the sealed keyspace and the etcd 3.5.17 release used to restore the snapshot
COPY . /tests/
RUN tar -xzf /tests/etcd-v3.5.17-linux-amd64.tar.gz -C /tmp \
    && install -m 0755 /tmp/etcd-v3.5.17-linux-amd64/etcd /tmp/etcd-v3.5.17-linux-amd64/etcdutl /usr/local/bin/ \
    && rm -rf /tmp/etcd-v3.5.17-linux-amd64 /tests/etcd-v3.5.17-linux-amd64.tar.gz

# parent dir of every declared artifact
RUN mkdir -p /app/out
