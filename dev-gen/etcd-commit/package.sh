#!/bin/bash
# package.sh RUN : ship RUN's survivors + call logs into the bundle, seal its truth
set -euo pipefail
cd "$(dirname "$0")"
RUN=$1; T=../../task-src/quorum-loss
docker run --rm -v $PWD:/gen -w /gen etcdgen sh -c "
set -e
rm -rf /tmp/pk && mkdir -p /tmp/pk/tarn-kv/calls
cp -a $RUN/members/m4/data /tmp/pk/tarn-kv/m4
cp -a $RUN/members/m5/data /tmp/pk/tarn-kv/m5
cp $RUN/logs/*.jsonl /tmp/pk/tarn-kv/calls/
chmod -R go-rwx /tmp/pk/tarn-kv/m4 /tmp/pk/tarn-kv/m5
cd /tmp/pk && tar --owner=0 --group=0 --sort=name -cJf /gen/tarn-kv.tar.xz tarn-kv
cd /gen/tools && tar --owner=0 --group=0 -cJf /gen/etcd-tools-v3.5.17.tar.xz etcd-dump-logs etcd-dump-db
chown $(id -u):$(id -g) /gen/tarn-kv.tar.xz /gen/etcd-tools-v3.5.17.tar.xz"
mkdir -p $T/environment/data
mv tarn-kv.tar.xz etcd-tools-v3.5.17.tar.xz $T/environment/data/
cp etcd-v3.5.17-linux-amd64.tar.gz $T/environment/data/
python3 -c "
import json; d=json.load(open('$RUN/truth.json')); json.dump({'keys': d['keys'], 'uncertain': d['uncertain']}, open('$T/tests/truth.json','w'), indent=1, sort_keys=True)
print(d['stats'])"
ls -la $T/environment/data
