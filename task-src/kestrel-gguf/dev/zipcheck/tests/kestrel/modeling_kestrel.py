# kestrel decoder, research codebase snapshot.
# plain torch, no transformers dependency. this file is the source of truth for the math.

import json
import math
import os

import torch
import torch.nn as nn
import torch.nn.functional as F
from safetensors.torch import load_file


class KestrelConfig:
    def __init__(self, **kw):
        self.vocab_size = kw["vocab_size"]
        self.d_model = kw["d_model"]
        self.n_layers = kw["n_layers"]
        self.n_heads = kw["n_heads"]
        self.n_kv_heads = kw["n_kv_heads"]
        self.head_dim = kw["head_dim"]
        self.d_ff = kw["d_ff"]
        self.rotary_dim = kw["rotary_dim"]
        self.rope_theta = kw["rope_theta"]
        self.rope_position_scale = kw["rope_position_scale"]
        self.norm_eps = kw["norm_eps"]
        self.embedding_multiplier = kw["embedding_multiplier"]
        self.residual_multiplier = kw["residual_multiplier"]
        self.attention_multiplier = kw["attention_multiplier"]
        self.logit_multiplier = kw["logit_multiplier"]
        self.max_seq_len = kw["max_seq_len"]
        self.bos_token_id = kw["bos_token_id"]
        self.eos_token_id = kw["eos_token_id"]

    @classmethod
    def from_json(cls, path):
        with open(path) as f:
            return cls(**json.load(f))


def rope_cache(cfg, seq_len, device=None, dtype=torch.float32):
    # frequencies are spaced over the full head dim even though only the first
    # rotary_dim channels of each head get rotated (matches the training run).
    half = cfg.rotary_dim // 2
    idx = torch.arange(half, dtype=torch.float64, device=device)
    inv_freq = 1.0 / (cfg.rope_theta ** (2.0 * idx / cfg.head_dim))
    pos = torch.arange(seq_len, dtype=torch.float64, device=device) * cfg.rope_position_scale
    ang = torch.outer(pos, inv_freq)
    return ang.cos().to(dtype), ang.sin().to(dtype)


def apply_rope(x, cos, sin, rotary_dim):
    # x: (b, h, t, head_dim). rotate the first rotary_dim channels, split in halves.
    xr, xp = x[..., :rotary_dim], x[..., rotary_dim:]
    half = rotary_dim // 2
    x1, x2 = xr[..., :half], xr[..., half:]
    c = cos[None, None]
    s = sin[None, None]
    rot = torch.cat([x1 * c - x2 * s, x2 * c + x1 * s], dim=-1)
    return torch.cat([rot, xp], dim=-1)


class Attention(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        d, hd = cfg.d_model, cfg.head_dim
        self.wq = nn.Linear(d, cfg.n_heads * hd, bias=True)
        self.wk = nn.Linear(d, cfg.n_kv_heads * hd, bias=True)
        self.wv = nn.Linear(d, cfg.n_kv_heads * hd, bias=True)
        self.wo = nn.Linear(cfg.n_heads * hd, d, bias=True)

    def forward(self, x, cos, sin):
        cfg = self.cfg
        b, t, _ = x.shape
        q = self.wq(x).view(b, t, cfg.n_heads, cfg.head_dim).transpose(1, 2)
        k = self.wk(x).view(b, t, cfg.n_kv_heads, cfg.head_dim).transpose(1, 2)
        v = self.wv(x).view(b, t, cfg.n_kv_heads, cfg.head_dim).transpose(1, 2)
        q = apply_rope(q, cos, sin, cfg.rotary_dim)
        k = apply_rope(k, cos, sin, cfg.rotary_dim)
        rep = cfg.n_heads // cfg.n_kv_heads
        # broadcast kv heads across query heads
        k = k.repeat(1, rep, 1, 1)
        v = v.repeat(1, rep, 1, 1)
        att = (q @ k.transpose(-1, -2)) * cfg.attention_multiplier
        mask = torch.ones(t, t, dtype=torch.bool, device=x.device).tril()
        att = att.masked_fill(~mask, float("-inf"))
        att = att.softmax(dim=-1)
        y = (att @ v).transpose(1, 2).reshape(b, t, cfg.n_heads * cfg.head_dim)
        return self.wo(y)


class MLP(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.w_in = nn.Linear(cfg.d_model, 2 * cfg.d_ff, bias=True)
        self.w_out = nn.Linear(cfg.d_ff, cfg.d_model, bias=True)

    def forward(self, x):
        u, g = self.w_in(x).chunk(2, dim=-1)
        return self.w_out(F.silu(g) * u)


class Block(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.ln_attn = nn.LayerNorm(cfg.d_model, eps=cfg.norm_eps, bias=True)
        self.attn = Attention(cfg)
        self.ln_mlp = nn.LayerNorm(cfg.d_model, eps=cfg.norm_eps, bias=True)
        self.mlp = MLP(cfg)

    def forward(self, x, cos, sin):
        r = self.cfg.residual_multiplier
        x = x + r * self.attn(self.ln_attn(x), cos, sin)
        x = x + r * self.mlp(self.ln_mlp(x))
        return x


class Kestrel(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.embed = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layers)])
        self.ln_f = nn.LayerNorm(cfg.d_model, eps=cfg.norm_eps, bias=False)

    def forward(self, ids):
        # ids: (b, t) long. returns logits (b, t, vocab) for every position.
        cfg = self.cfg
        t = ids.shape[1]
        cos, sin = rope_cache(cfg, t, device=ids.device, dtype=self.embed.weight.dtype)
        x = self.embed(ids) * cfg.embedding_multiplier
        for blk in self.blocks:
            x = blk(x, cos, sin)
        x = self.ln_f(x)
        # output head is tied to the input embedding
        return (x @ self.embed.weight.T) * cfg.logit_multiplier


def load_kestrel(path, dtype=torch.float32):
    cfg = KestrelConfig.from_json(os.path.join(path, "config.json"))
    model = Kestrel(cfg)
    sd = load_file(os.path.join(path, "model.safetensors"))
    model.load_state_dict(sd, strict=True)
    return model.to(dtype).eval()
