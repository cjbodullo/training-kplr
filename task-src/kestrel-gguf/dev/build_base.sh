#!/usr/bin/env bash
cd "$(dirname "$0")"
for i in 1 2 3; do
  docker build --network host -f base.Dockerfile -t kestrel-base . > build_base.$i.log 2>&1
  rc=$?
  [ $rc -eq 0 ] && { echo BUILD_OK >> build.status; exit 0; }
  echo "attempt $i failed rc=$rc" >> build.status
done
echo BUILD_FAIL >> build.status
