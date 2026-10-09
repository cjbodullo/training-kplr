"""grades /app/kestrel.gguf: stock llama.cpp b10964 must tokenize like the kestrel tokenizer.json
and reproduce the kestrel pytorch model's next token distribution on sealed texts."""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pytest
import torch
from tokenizers import Tokenizer

import gguf

ART = "/app/kestrel.gguf"
REF = "/tests/kestrel"
PROMPTS = sorted(glob.glob("/tests/prompts/*.txt"))
DUMPER = "/usr/local/bin/kestrel-logits"
# max abs difference of log softmax (nats), any position, any vocab entry
TOL = 5e-3
MAX_BYTES = 256 * 1024 * 1024

sys.path.insert(0, REF)
from modeling_kestrel import load_kestrel  # noqa: E402

torch.set_num_threads(4)


@pytest.fixture(scope="session")
def work():
    assert os.path.isfile(ART), f"{ART} missing"
    assert os.path.getsize(ART) <= MAX_BYTES, "gguf larger than 256 MiB"
    d = tempfile.mkdtemp(prefix="kestrel-grade-")
    os.chmod(d, 0o777)
    shutil.copyfile(ART, os.path.join(d, "model.gguf"))
    os.chmod(os.path.join(d, "model.gguf"), 0o644)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def ref_model():
    return load_kestrel(REF, dtype=torch.float64)


@pytest.fixture(scope="session")
def hf_tok():
    return Tokenizer.from_file(os.path.join(REF, "tokenizer.json"))


def run_dumper(work, prompt_path):
    name = os.path.basename(prompt_path)
    txt = os.path.join(work, name)
    shutil.copyfile(prompt_path, txt)
    os.chmod(txt, 0o644)
    out = os.path.join(work, name + ".bin")
    # the gguf is untrusted input to libllama: parse it as nobody
    cmd = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups",
           DUMPER, os.path.join(work, "model.gguf"), txt, out]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=work)
    assert p.returncode == 0, f"kestrel-logits failed ({p.returncode}): {p.stderr[-2000:]}"
    raw = open(out, "rb").read()
    n, nv = np.frombuffer(raw[:8], dtype=np.int32)
    ids = np.frombuffer(raw[8:8 + 4 * n], dtype=np.int32).astype(np.int64)
    logits = np.frombuffer(raw[8 + 4 * n:], dtype=np.float32)
    assert logits.size == n * nv, "truncated logits dump"
    os.remove(out)
    return ids, logits.reshape(n, nv)


def test_sealed_prompts_present():
    assert len(PROMPTS) >= 16


def test_gguf_tensors_are_f32():
    r = gguf.GGUFReader(ART)
    bad = [t.name for t in r.tensors if t.tensor_type != gguf.GGMLQuantizationType.F32]
    assert not bad, f"non f32 tensors: {bad[:10]}"
    assert len(r.tensors) > 0


@pytest.mark.parametrize("prompt", PROMPTS, ids=[os.path.basename(p)[:-4] for p in PROMPTS])
def test_prompt(prompt, work, ref_model, hf_tok):
    text = open(prompt, encoding="utf-8", newline="").read()
    want = hf_tok.encode(text).ids
    ids, logits = run_dumper(work, prompt)
    first = next((i for i, (a, b) in enumerate(zip(ids.tolist(), want)) if a != b), min(len(ids), len(want)))
    assert ids.tolist() == want, (
        f"token ids differ: llama.cpp gave {len(ids)} tokens, tokenizer.json gives {len(want)}; first difference at {first}")
    assert logits.shape[1] == ref_model.cfg.vocab_size, f"n_vocab {logits.shape[1]}"
    with torch.no_grad():
        ref = torch.log_softmax(ref_model(torch.tensor([want]))[0], dim=-1).numpy()
    got = torch.log_softmax(torch.from_numpy(logits.astype(np.float64)), dim=-1).numpy()
    assert np.isfinite(got).all(), "non finite logits"
    err = np.abs(got - ref).max(axis=1)
    worst = int(err.argmax())
    assert err.max() <= TOL, f"log softmax off by {err.max():.4g} at position {worst} of {len(want)}"
