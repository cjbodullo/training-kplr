"""dev: repack the kestrel checkpoint into the 'kite' training framework layout shipped to the agent.

kite layout (the truth the agent has to recover):
  attn.wqkv  rows packed per kv group g: [q(g,0) .. q(g,rep-1), k(g), v(g)], hd rows each.
             q(g,r) is attention head r*n_kv + g, and wo consumes heads in head index order.
  mlp.w_in   rows [up ; gate]
  rope       first rotary_dim channels of a head, half split, inv_freq over head_dim
"""
import json
import os
import sys

import numpy as np
from safetensors.numpy import load_file, save_file

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "kestrel")
DST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "kite_ckpt")

cfg = json.load(open(os.path.join(SRC, "config.json")))
sd = load_file(os.path.join(SRC, "model.safetensors"))
H, KV, hd = cfg["n_heads"], cfg["n_kv_heads"], cfg["head_dim"]
rep = H // KV


def pack_qkv(q, k, v):
    q = q.reshape(H, hd, *q.shape[1:])
    k = k.reshape(KV, hd, *k.shape[1:])
    v = v.reshape(KV, hd, *v.shape[1:])
    rows = []
    for g in range(KV):
        for r in range(rep):
            rows.append(q[r * KV + g])
        rows.append(k[g])
        rows.append(v[g])
    return np.concatenate(rows, axis=0)


out = {"tok_emb.weight": sd["embed.weight"], "ln_f.weight": sd["ln_f.weight"]}
for i in range(cfg["n_layers"]):
    p, o = f"blocks.{i}.", f"layers.{i}."
    out[o + "ln1.weight"] = sd[p + "ln_attn.weight"]
    out[o + "ln1.bias"] = sd[p + "ln_attn.bias"]
    out[o + "attn.wqkv.weight"] = pack_qkv(sd[p + "attn.wq.weight"], sd[p + "attn.wk.weight"], sd[p + "attn.wv.weight"])
    out[o + "attn.wqkv.bias"] = pack_qkv(sd[p + "attn.wq.bias"], sd[p + "attn.wk.bias"], sd[p + "attn.wv.bias"])
    out[o + "attn.wo.weight"] = sd[p + "attn.wo.weight"]
    out[o + "attn.wo.bias"] = sd[p + "attn.wo.bias"]
    out[o + "ln2.weight"] = sd[p + "ln_mlp.weight"]
    out[o + "ln2.bias"] = sd[p + "ln_mlp.bias"]
    out[o + "mlp.w_in.weight"] = sd[p + "mlp.w_in.weight"]
    out[o + "mlp.w_in.bias"] = sd[p + "mlp.w_in.bias"]
    out[o + "mlp.w_out.weight"] = sd[p + "mlp.w_out.weight"]
    out[o + "mlp.w_out.bias"] = sd[p + "mlp.w_out.bias"]

os.makedirs(DST, exist_ok=True)
save_file({k: np.ascontiguousarray(v) for k, v in out.items()}, os.path.join(DST, "model.safetensors"),
          metadata={"framework": "kite 0.9.3", "step": "600"})
yaml = f"""# kite 0.9.3 run config (exported from the run dir, run kestrel-6m-r3)
run_name: kestrel-6m-r3
model:
  family: kestrel
  vocab_size: {cfg['vocab_size']}
  d_model: {cfg['d_model']}
  n_layers: {cfg['n_layers']}
  n_heads: {H}
  n_kv_heads: {KV}
  d_head: {hd}
  d_ff: {cfg['d_ff']}
  norm: layernorm
  norm_eps: 1.0e-05
  final_norm_bias: false
  mlp: swiglu_fused
  qkv: fused_grouped
  bias: true
  tie_embeddings: true
  max_seq_len: {cfg['max_seq_len']}
  rotary:
    pct: {cfg['rotary_dim'] / hd}
    theta: {cfg['rope_theta']}
    interp_factor: {1.0 / cfg['rope_position_scale']}
    cache_dtype: bfloat16
  mup:
    input_alpha: {cfg['embedding_multiplier']}
    residual_alpha: {cfg['residual_multiplier']}
    attn_temperature: inverse_d
    output_alpha: {cfg['logit_multiplier']}
tokenizer:
  path: tokenizer.json
  bos_id: {cfg['bos_token_id']}
  eos_id: {cfg['eos_token_id']}
train:
  seq_len: 128
  global_batch: 16
  steps: 600
  lr: 2.0e-3
  schedule: cosine
  warmup: 100
  optimizer: adamw
  betas: [0.9, 0.95]
  weight_decay: 0.05
  grad_clip: 1.0
  dtype: float32
"""
open(os.path.join(DST, "train_config.yaml"), "w").write(yaml)
import shutil
shutil.copy(os.path.join(SRC, "tokenizer.json"), os.path.join(DST, "tokenizer.json"))
print("wrote", DST, len(out), "tensors")
