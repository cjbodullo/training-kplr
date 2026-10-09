"""dev grader: python3 check.py model.gguf prompts_dir [ref_dir]. prints per prompt tok match + max err."""
import glob
import os
import subprocess
import sys
import tempfile

import numpy as np
import torch
from tokenizers import Tokenizer

gg, pdir = sys.argv[1], sys.argv[2]
ref_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "kestrel")
sys.path.insert(0, ref_dir)
from modeling_kestrel import load_kestrel  # noqa

torch.set_num_threads(4)
m = load_kestrel(ref_dir, torch.float64)
tok = Tokenizer.from_file(os.path.join(ref_dir, "tokenizer.json"))
worst = 0.0
allok = True
for p in sorted(glob.glob(os.path.join(pdir, "*.txt"))):
    text = open(p, encoding="utf-8", newline="").read()
    want = tok.encode(text).ids
    out = tempfile.mktemp()
    r = subprocess.run(["kestrel-logits", gg, p, out], capture_output=True, text=True)
    name = os.path.basename(p)[:-4]
    if r.returncode:
        print(f"{name:14s} DUMPER FAIL {r.stderr.strip()[-200:]}"); allok = False; continue
    raw = open(out, "rb").read(); os.remove(out)
    n, nv = np.frombuffer(raw[:8], np.int32)
    ids = np.frombuffer(raw[8:8 + 4 * n], np.int32).tolist()
    lg = np.frombuffer(raw[8 + 4 * n:], np.float32).reshape(n, nv)
    if ids != want:
        i = next((i for i, (a, b) in enumerate(zip(ids, want)) if a != b), min(len(ids), len(want)))
        print(f"{name:14s} TOKENS DIFFER n={len(ids)} vs {len(want)} first@{i}"); allok = False; continue
    with torch.no_grad():
        ref = torch.log_softmax(m(torch.tensor([want]))[0], -1).numpy()
    got = torch.log_softmax(torch.from_numpy(lg.astype(np.float64)), -1).numpy()
    e = np.abs(got - ref).max(1)
    worst = max(worst, e.max())
    print(f"{name:14s} n={n:5d} maxerr={e.max():.3e} @ {e.argmax()} median={np.median(e):.2e}")
print(f"WORST {worst:.4e} tokens_all_ok={allok}")
