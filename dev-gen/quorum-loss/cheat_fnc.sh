#!/usr/bin/env bash
# shortcut: textbook dr. boot the most complete survivor with --force-new-cluster and snapshot it.
# $1 = m4 or m5
set -e
rm -rf /tmp/fnc && cp -a /data/tarn-kv/$1 /tmp/fnc
etcd --name $1 --data-dir /tmp/fnc --force-new-cluster --listen-client-urls http://127.0.0.1:12379 \
  --advertise-client-urls http://127.0.0.1:12379 --listen-peer-urls http://127.0.0.1:12380 \
  --initial-advertise-peer-urls http://127.0.0.1:12380 > /tmp/fnc.log 2>&1 &
for i in $(seq 60); do etcdctl --endpoints=http://127.0.0.1:12379 endpoint health >/dev/null 2>&1 && break; sleep 0.5; done
mkdir -p /app/out && rm -f /app/out/restore.db
etcdctl --endpoints=http://127.0.0.1:12379 snapshot save /app/out/restore.db >/dev/null
: > /app/out/uncertain.txt
