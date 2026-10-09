"""dev: regression transcripts from the true model (greedy, fp64), then check every menu hypothesis
against them. usage: python make_transcripts.py <kite_ckpt_dir>"""
import glob
import json
import os
import random
import sys

import torch
from tokenizers import Tokenizer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "kestrel"))
sys.path.insert(0, HERE)
from modeling_kestrel import load_kestrel  # noqa: E402
from hypo import Kite, TRUE, near_hypotheses  # noqa: E402

CK = sys.argv[1]
N_PROMPTS, N_LONG, GEN, MARGIN, TOPK = 24, 8, 32, 0.05, 5
torch.set_num_threads(8)
tok = Tokenizer.from_file(os.path.join(CK, "tokenizer.json"))
ref = load_kestrel(os.path.join(HERE, "kestrel"), torch.float64)
kite = Kite(CK)
rng = random.Random(4242)

# sanity: kite TRUE convention == modeling_kestrel
ids = torch.tensor([tok.encode("The night was cold, and 42 ships waited.").ids])
with torch.no_grad():
    assert (kite.forward(ids, TRUE) - ref(ids)).abs().max() < 1e-9, "TRUE convention mismatch"

texts = []
for f in sorted(glob.glob(os.path.join(HERE, "corpus", "*.txt"))):
    t = open(f, encoding="utf-8").read()
    texts.append(t[len(t) // 10: -len(t) // 10])
recs = []
while len(recs) < N_PROMPTS:
    src = rng.choice(texts)
    s = rng.randrange(0, len(src) - 17000)
    s = src.find(" ", s) + 1
    long_ = len(recs) < N_LONG
    plen = rng.randint(800, 1800) if long_ else rng.randint(40, 160)
    pid = tok.encode(src[s:s + 16000]).ids[:plen]
    prompt = tok.decode(pid[1:])
    pid = tok.encode(prompt).ids
    cur = list(pid)
    gen = []
    with torch.no_grad():
        for _ in range(GEN):
            lg = ref(torch.tensor([cur]))[0, -1]
            top = lg.topk(2).values
            if (top[0] - top[1]).item() < MARGIN:
                break
            nxt = int(lg.argmax())
            gen.append(nxt)
            cur.append(nxt)
    if len(gen) < 12:
        continue
    with torch.no_grad():
        lp = torch.log_softmax(ref(torch.tensor([pid + gen]))[0], -1)[len(pid) - 1:-1]
    top = [[[int(i), round(float(v), 5)] for v, i in zip(*row.topk(TOPK))] for row in lp]
    recs.append({"prompt": prompt, "completion": tok.decode(gen), "prompt_ids": pid, "completion_ids": gen,
                 "top_logprobs": top})
print("transcripts", len(recs), "tokens", sum(len(r["completion_ids"]) for r in recs))
json.dump(recs, open(os.path.join(HERE, "transcripts_dev.json"), "w"), ensure_ascii=False)

# identifiability: teacher forced argmax agreement per hypothesis
res = []
for h in near_hypotheses():
    bad = 0
    with torch.no_grad():
        for r in recs:
            seq = torch.tensor([r["prompt_ids"] + r["completion_ids"]])
            lg = kite.forward(seq, h)[0]
            n = len(r["prompt_ids"])
            pred = lg[n - 1:-1].argmax(-1).tolist()
            bad += sum(int(a != b) for a, b in zip(pred, r["completion_ids"]))
            lp = torch.log_softmax(lg[n - 1:-1], -1)
            for row, top in zip(lp, r["top_logprobs"]):
                for i, v in top:
                    lpd = max(lpd, abs(float(row[i]) - v)) if 'lpd' in dir() else abs(float(row[i]) - v)
    res.append((bad, h, lpd)); del lpd
res.sort(key=lambda x: (x[0], x[2]))
for bad, h, lpd in res[:8]:
    print(bad, round(lpd, 6), h, "<- TRUE" if h == TRUE else "")
print("hypotheses reproducing tokens AND logprobs (<2e-5):", sum(1 for b, _, l in res if b == 0 and l < 2e-5), "of", len(res))
for bad, h, lpd in res:
    if h == {**TRUE, 'rope_cache': 'none'} or h == {**TRUE, 'rope_cache': 'cossin_bf16'}:
        print('rope_cache variant', h['rope_cache'], 'mismatches', bad, 'max logprob diff', round(lpd, 5))
