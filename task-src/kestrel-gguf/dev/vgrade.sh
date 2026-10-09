#!/usr/bin/env bash
# dev: grade a gguf (or nothing) through the sealed verifier image. usage: vgrade.sh <name> [file.gguf]
name=$1; f=${2:-}
mkdir -p vlogs/$name
args=(--rm --network none -v "$PWD/vlogs/$name:/logs/verifier")
[ -n "$f" ] && args+=(-v "$(realpath $f):/app/kestrel.gguf:ro")
docker run "${args[@]}" kestrel-tests bash /tests/test.sh > vlogs/$name/run.txt 2>&1
echo "$name reward=$(cat vlogs/$name/reward.txt) $(grep -c PASSED vlogs/$name/pytest.txt) passed $(grep -c FAILED vlogs/$name/pytest.txt) failed"
