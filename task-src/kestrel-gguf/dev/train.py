"""short cpu training run that produces the kestrel checkpoint shipped to the agent (dev only)."""
import glob
import json
import math
import os
import sys
import time

import torch
from safetensors.torch import save_file
from tokenizers import Tokenizer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "kestrel"))
from modeling_kestrel import Kestrel, KestrelConfig  # noqa: E402

OUT = os.path.join(HERE, "kestrel")
STEPS = int(os.environ.get("STEPS", "1500"))
SEQ = int(os.environ.get("SEQ", "128"))
BATCH = int(os.environ.get("BATCH", "16"))

cfg_d = dict(
    vocab_size=4096, d_model=256, n_layers=6, n_heads=8, n_kv_heads=2, head_dim=32, d_ff=704,
    rotary_dim=16, rope_theta=10000.0, rope_position_scale=0.5, norm_eps=1e-5,
    embedding_multiplier=6.0, residual_multiplier=0.35, attention_multiplier=1.0 / 32,
    logit_multiplier=0.25, max_seq_len=2048, bos_token_id=1, eos_token_id=2,
)

torch.manual_seed(20261008)
torch.set_num_threads(os.cpu_count())
tok = Tokenizer.from_file(os.path.join(OUT, "tokenizer.json"))
text = ""
for f in sorted(glob.glob(os.path.join(HERE, "corpus", "*.txt"))):
    text += open(f, encoding="utf-8").read() + "\n"
ids = torch.tensor(tok.encode(text, add_special_tokens=False).ids, dtype=torch.long)
print("corpus tokens", len(ids), flush=True)

cfg = KestrelConfig(**cfg_d)
model = Kestrel(cfg)
with torch.no_grad():
    for n, p in model.named_parameters():
        if n.endswith("bias"):
            p.normal_(0.0, 0.05)
        elif "ln" in n:
            p.normal_(1.0, 0.1)
        elif p.dim() == 2:
            p.normal_(0.0, 0.02 if "embed" not in n else 0.05)
    # give the embedding table a shared offset, residual streams in this family are not centered
    model.embed.weight.add_(torch.randn(cfg.d_model) * 0.03)

opt = torch.optim.AdamW(model.parameters(), lr=2e-3, betas=(0.9, 0.95), weight_decay=0.05)
sched = torch.optim.lr_scheduler.LambdaLR(
    opt, lambda s: min(1.0, (s + 1) / 100) * 0.5 * (1 + math.cos(math.pi * min(s, STEPS) / STEPS)))
CK = os.path.join(HERE, "train_ckpt.pt")
start = 0
if os.path.exists(CK):
    ck = torch.load(CK, weights_only=False)
    model.load_state_dict(ck['model']); opt.load_state_dict(ck['opt']); sched.load_state_dict(ck['sched'])
    torch.set_rng_state(ck['rng']); start = ck['step']
    print('resumed at', start, flush=True)
t0 = time.time()
for step in range(start, STEPS):
    ix = torch.randint(0, len(ids) - SEQ - 1, (BATCH,))
    x = torch.stack([ids[i:i + SEQ] for i in ix])
    y = torch.stack([ids[i + 1:i + SEQ + 1] for i in ix])
    x[:, 0] = cfg.bos_token_id
    logits = model(x)
    loss = torch.nn.functional.cross_entropy(logits.reshape(-1, cfg.vocab_size), y.reshape(-1))
    opt.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    opt.step()
    sched.step()
    if (step + 1) % 50 == 0:
        torch.save({'model': model.state_dict(), 'opt': opt.state_dict(), 'sched': sched.state_dict(),
                    'rng': torch.get_rng_state(), 'step': step + 1}, CK + '.tmp')
        os.replace(CK + '.tmp', CK)
    if step % 50 == 0 or step == STEPS - 1:
        print(f"step {step} loss {loss.item():.4f} t {time.time() - t0:.0f}s", flush=True)

sd = {k: v.detach().contiguous().clone() for k, v in model.state_dict().items()}
save_file(sd, os.path.join(OUT, "model.safetensors"), metadata={"format": "pt", "step": str(STEPS)})
with open(os.path.join(OUT, "config.json"), "w") as f:
    json.dump(cfg_d, f, indent=2)
print("saved", OUT)
