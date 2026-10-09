#!/usr/bin/env bash
# dev: regenerate prompts + reference gguf, then grade every single-rewrite ablation
set -u
cd /t/dev
python make_prompts.py > prompts.log 2>&1
mkdir -p abl
python ../solution/convert.py kestrel abl/ref.gguf > /dev/null
echo "== ref"; python check.py abl/ref.gguf prompts_candidates | tail -1
for a in no_center no_beta no_qperm no_chanperm no_partial no_posscale no_qscale no_resid tied; do
  ABLATE=$a python convert_ablate.py kestrel abl/$a.gguf > /dev/null 2>&1
  echo "== $a"; python check.py abl/$a.gguf prompts_candidates | awk '{print $1, $3, $4}' | tr '\n' ';' ; echo
done
for p in llama-bpe gpt2 starcoder deepseek-coder; do
  PRE=$p python convert_ablate.py kestrel abl/pre_$p.gguf > /dev/null 2>&1
  echo "== pre=$p"; python check.py abl/pre_$p.gguf prompts_candidates | grep -c "TOKENS DIFFER"
done
