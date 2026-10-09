#!/usr/bin/env python3
"""kestrel -> stock llama.cpp gguf (arch "llama"), exact reparameterisation.

what does not exist in llama.cpp's llama graph, and how it is rewritten:
  layernorm (mean + bias)   residual stream is kept mean free (embeddings, attn out and ffn down
                            projected onto the centered subspace), so layernorm == rmsnorm; the
                            layernorm bias is pushed into the next linear layer's bias.
  partial rotary, half split llama rotates every adjacent pair of every channel and refuses
                            n_rot != head_dim. head channels are interleaved (j, j+rot/2) so the
                            rotated pairs line up, and rope_freqs gives the unrotated pairs a
                            huge divisor (angle 0). rotary positions are scaled by 0.5 through
                            the same factors.
  inv_freq over head_dim    llama uses base^(-2i/n_rot) with n_rot = head_dim, which is exactly
                            the kestrel spacing once the channels are interleaved.
  tiled kv heads            kestrel uses kv head (h mod n_kv) for query head h, llama.cpp uses
                            h // (n_head / n_kv). query heads (and wo columns) are regrouped.
  attention multiplier      1/head_dim instead of 1/sqrt(head_dim): folded into wq, bq.
  residual multiplier       folded into wo, bo, w_down, b_down.
  embedding multiplier      folded into token_embd; the head is untied (output.weight carries
                            the raw embedding times the logit multiplier).
"""
import json
import os
import sys

import numpy as np
from safetensors.numpy import load_file
import gguf

import yaml

SRC = sys.argv[1] if len(sys.argv) > 1 else "/app/kestrel"
DST = sys.argv[2] if len(sys.argv) > 2 else "/app/kestrel.gguf"

# ---- read the kite run dir. layout facts recovered from the regression transcripts:
#   wqkv packed per kv group g as [q(g,0)..q(g,rep-1), k(g), v(g)], q(g,r) = head r*n_kv + g
#   (so query head h reads kv head h mod n_kv), w_in = [up; gate], rope on the first
#   pct*d_head channels in half split layout with inv_freq spaced over d_head,
#   attn_temperature inverse_d = 1/d_head, positions divided by interp_factor.
mc = yaml.safe_load(open(os.path.join(SRC, "train_config.yaml")))["model"]
raw = {k: v.astype(np.float64) for k, v in load_file(os.path.join(SRC, "model.safetensors")).items()}
cfg = dict(vocab_size=mc["vocab_size"], d_model=mc["d_model"], n_layers=mc["n_layers"],
           n_heads=mc["n_heads"], n_kv_heads=mc["n_kv_heads"], head_dim=mc["d_head"], d_ff=mc["d_ff"],
           rotary_dim=int(round(mc["rotary"]["pct"] * mc["d_head"])), rope_theta=mc["rotary"]["theta"],
           rope_position_scale=1.0 / mc["rotary"]["interp_factor"], norm_eps=float(mc["norm_eps"]),
           embedding_multiplier=mc["mup"]["input_alpha"], residual_multiplier=mc["mup"]["residual_alpha"],
           attention_multiplier=1.0 / mc["d_head"], logit_multiplier=mc["mup"]["output_alpha"],
           max_seq_len=mc["max_seq_len"])
tcfg = yaml.safe_load(open(os.path.join(SRC, "train_config.yaml")))["tokenizer"]
cfg["bos_token_id"], cfg["eos_token_id"] = tcfg["bos_id"], tcfg["eos_id"]


def unpack_qkv(w):
    H_, KV_, hd_ = cfg["n_heads"], cfg["n_kv_heads"], cfg["head_dim"]
    rep_ = H_ // KV_
    blocks = w.reshape(H_ + 2 * KV_, hd_, *w.shape[1:])
    q, k, v = [None] * H_, [], []
    for g in range(KV_):
        base = g * (rep_ + 2)
        for r_ in range(rep_):
            q[r_ * KV_ + g] = blocks[base + r_]
        k.append(blocks[base + rep_])
        v.append(blocks[base + rep_ + 1])
    cat = lambda xs: np.concatenate(xs, axis=0)
    return cat(q), cat(k), cat(v)


sd = {"embed.weight": raw["tok_emb.weight"], "ln_f.weight": raw["ln_f.weight"]}
for i in range(cfg["n_layers"]):
    p, o = f"blocks.{i}.", f"layers.{i}."
    wq, wk, wv = unpack_qkv(raw[o + "attn.wqkv.weight"])
    bq_, bk_, bv_ = unpack_qkv(raw[o + "attn.wqkv.bias"])
    sd.update({p + "ln_attn.weight": raw[o + "ln1.weight"], p + "ln_attn.bias": raw[o + "ln1.bias"],
               p + "attn.wq.weight": wq, p + "attn.wk.weight": wk, p + "attn.wv.weight": wv,
               p + "attn.wq.bias": bq_, p + "attn.wk.bias": bk_, p + "attn.wv.bias": bv_,
               p + "attn.wo.weight": raw[o + "attn.wo.weight"], p + "attn.wo.bias": raw[o + "attn.wo.bias"],
               p + "ln_mlp.weight": raw[o + "ln2.weight"], p + "ln_mlp.bias": raw[o + "ln2.bias"],
               p + "mlp.w_in.weight": raw[o + "mlp.w_in.weight"], p + "mlp.w_in.bias": raw[o + "mlp.w_in.bias"],
               p + "mlp.w_out.weight": raw[o + "mlp.w_out.weight"], p + "mlp.w_out.bias": raw[o + "mlp.w_out.bias"]})

d = cfg["d_model"]
L = cfg["n_layers"]
H = cfg["n_heads"]
KV = cfg["n_kv_heads"]
hd = cfg["head_dim"]
ff = cfg["d_ff"]
rot = cfg["rotary_dim"]
rep = H // KV
r = cfg["residual_multiplier"]

C = np.eye(d) - np.full((d, d), 1.0 / d)   # projector onto mean free vectors


def center_rows_out(w):
    """w maps into the residual stream (shape (d, n) or (d,)); project its output."""
    return C @ w


# channel permutation inside a head: new 2j <- old j, new 2j+1 <- old j + rot/2 (j < rot/2),
# unrotated channels follow in order and land in pairs whose angle is forced to 0.
half = rot // 2
chan = []
for j in range(half):
    chan += [j, j + half]
chan += list(range(rot, hd))
chan = np.array(chan)
assert sorted(chan.tolist()) == list(range(hd))

# query head order so that new head i reads kv head i // rep
qhead = [g + k * KV for g in range(KV) for k in range(rep)]


def permute_heads(w, heads, nheads):
    """w: (nheads*hd, ...) rows grouped by head. reorder heads, then channels in each head."""
    w = w.reshape(nheads, hd, *w.shape[1:])
    w = w[heads]
    w = w[:, chan]
    return w.reshape(nheads * hd, *w.shape[2:])


tensors = {}
E = sd["embed.weight"]
tensors["token_embd.weight"] = (E * cfg["embedding_multiplier"]) @ C.T
tensors["output.weight"] = E * cfg["logit_multiplier"]
tensors["output_norm.weight"] = sd["ln_f.weight"]

# rope factors: angle = pos * base^(-2i/n_rot) / factor. kestrel rotates at pos * 0.5.
factors = np.full(hd // 2, 1e30)
factors[:half] = 1.0 / cfg["rope_position_scale"]
tensors["rope_freqs.weight"] = factors

qscale = cfg["attention_multiplier"] * np.sqrt(hd)
for i in range(L):
    p = f"blocks.{i}."
    ga, ba = sd[p + "ln_attn.weight"], sd[p + "ln_attn.bias"]
    gm, bm = sd[p + "ln_mlp.weight"], sd[p + "ln_mlp.bias"]
    wq, bq = sd[p + "attn.wq.weight"], sd[p + "attn.wq.bias"]
    wk, bk = sd[p + "attn.wk.weight"], sd[p + "attn.wk.bias"]
    wv, bv = sd[p + "attn.wv.weight"], sd[p + "attn.wv.bias"]
    wo, bo = sd[p + "attn.wo.weight"], sd[p + "attn.wo.bias"]
    w_in, b_in = sd[p + "mlp.w_in.weight"], sd[p + "mlp.w_in.bias"]
    w_out, b_out = sd[p + "mlp.w_out.weight"], sd[p + "mlp.w_out.bias"]

    # layernorm bias -> following biases
    bq = bq + wq @ ba
    bk = bk + wk @ ba
    bv = bv + wv @ ba
    wu, wg = w_in[:ff], w_in[ff:]
    bu, bg = b_in[:ff] + wu @ bm, b_in[ff:] + wg @ bm

    q_w = permute_heads(wq * qscale, qhead, H)
    q_b = permute_heads(bq * qscale, qhead, H)
    k_w = permute_heads(wk, list(range(KV)), KV)
    k_b = permute_heads(bk, list(range(KV)), KV)

    # wo columns follow the query head order (channels untouched: v is not rotated)
    wo_cols = wo.reshape(d, H, hd)[:, qhead].reshape(d, H * hd)

    b = f"blk.{i}."
    tensors[b + "attn_norm.weight"] = ga
    tensors[b + "attn_q.weight"] = q_w
    tensors[b + "attn_q.bias"] = q_b
    tensors[b + "attn_k.weight"] = k_w
    tensors[b + "attn_k.bias"] = k_b
    tensors[b + "attn_v.weight"] = wv
    tensors[b + "attn_v.bias"] = bv
    tensors[b + "attn_output.weight"] = r * center_rows_out(wo_cols)
    tensors[b + "attn_output.bias"] = r * center_rows_out(bo)
    tensors[b + "ffn_norm.weight"] = gm
    tensors[b + "ffn_up.weight"] = wu
    tensors[b + "ffn_up.bias"] = bu
    tensors[b + "ffn_gate.weight"] = wg
    tensors[b + "ffn_gate.bias"] = bg
    tensors[b + "ffn_down.weight"] = r * center_rows_out(w_out)
    tensors[b + "ffn_down.bias"] = r * center_rows_out(b_out)

# ---- tokenizer: byte level bpe, split regex is the qwen2 one (single digits) ----
tj = json.load(open(os.path.join(SRC, "tokenizer.json"), encoding="utf-8"))
vocab = tj["model"]["vocab"]
added = {a["content"]: a for a in tj.get("added_tokens", [])}
n_vocab = cfg["vocab_size"]
assert len(vocab) == n_vocab
tokens = [None] * n_vocab
for t, i in vocab.items():
    tokens[i] = t
types = [gguf.TokenType.CONTROL if t in added and added[t].get("special") else gguf.TokenType.NORMAL
         for t in tokens]
merges = [m if isinstance(m, str) else " ".join(m) for m in tj["model"]["merges"]]

w = gguf.GGUFWriter(DST, "llama")
w.add_name("kestrel")
w.add_context_length(cfg["max_seq_len"])
w.add_embedding_length(d)
w.add_block_count(L)
w.add_feed_forward_length(ff)
w.add_head_count(H)
w.add_head_count_kv(KV)
w.add_rope_dimension_count(hd)
w.add_rope_freq_base(cfg["rope_theta"])
w.add_layer_norm_rms_eps(cfg["norm_eps"])
w.add_vocab_size(n_vocab)
w.add_file_type(gguf.LlamaFileType.ALL_F32)
w.add_tokenizer_model("gpt2")
w.add_tokenizer_pre("qwen2")
w.add_token_list(tokens)
w.add_token_types(types)
w.add_token_merges(merges)
w.add_bos_token_id(cfg["bos_token_id"])
w.add_eos_token_id(cfg["eos_token_id"])
w.add_pad_token_id(0)
w.add_add_bos_token(True)
w.add_add_eos_token(False)
for name, arr in tensors.items():
    w.add_tensor(name, np.ascontiguousarray(arr, dtype=np.float32))
w.write_header_to_file()
w.write_kv_data_to_file()
w.write_tensors_to_file()
w.close()
print("wrote", DST, len(tensors), "tensors")
