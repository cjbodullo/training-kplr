"""dev: forward pass of a kite checkpoint under a chosen set of layout conventions.
TRUE is what the training code actually did; the menu is what a reverse engineer would try."""
import itertools
import os

import numpy as np
import torch
import torch.nn.functional as F
import yaml
from safetensors.torch import load_file

TRUE = dict(pack="group", head_order="tile", mlp="up_gate", rope_layout="half",
            rope_place="first", denom="head", attn_temp="dhead", rope_cache="inv_bf16")
MENU = dict(pack=["group", "flat", "group_kvfirst"], head_order=["tile", "contig"],
            mlp=["up_gate", "gate_up"], rope_layout=["half", "interleave"],
            rope_place=["first", "last"], denom=["head", "rot"],
            attn_temp=["dhead", "dmodel", "sqrt"], rope_cache=["inv_bf16", "none", "cossin_bf16"])


def all_hypotheses():
    keys = list(MENU)
    for vals in itertools.product(*[MENU[k] for k in keys]):
        yield dict(zip(keys, vals))


def near_hypotheses():
    """TRUE, every single deviation, and every pair of deviations that involves rope_cache."""
    seen = []
    def add(h):
        if h not in seen:
            seen.append(h)
    add(dict(TRUE))
    for k, vs in MENU.items():
        for v in vs:
            add({**TRUE, k: v})
    for k, vs in MENU.items():
        if k == "rope_cache":
            continue
        for v in vs:
            for rc in MENU["rope_cache"]:
                add({**TRUE, k: v, "rope_cache": rc})
    return seen


class Kite:
    def __init__(self, ckpt_dir, dtype=torch.float64):
        c = yaml.safe_load(open(os.path.join(ckpt_dir, "train_config.yaml")))["model"]
        self.c = c
        self.sd = {k: v.to(dtype) for k, v in load_file(os.path.join(ckpt_dir, "model.safetensors")).items()}
        self.dtype = dtype

    def unpack_qkv(self, w, h):
        c = self.c
        H, KV, hd = c["n_heads"], c["n_kv_heads"], c["d_head"]
        rep = H // KV
        blocks = list(w.reshape(H + 2 * KV, hd, *w.shape[1:]))
        q = [None] * H
        k = [None] * KV
        v = [None] * KV
        if h["pack"] == "flat":
            qs, ks, vs = blocks[:H], blocks[H:H + KV], blocks[H + KV:]
            # flat packing: q heads already in head index order
            return torch.stack(qs).reshape(H * hd, *w.shape[1:]), torch.stack(ks).reshape(KV * hd, *w.shape[1:]), \
                torch.stack(vs).reshape(KV * hd, *w.shape[1:]), "flat"
        it = iter(blocks)
        for g in range(KV):
            grp = [next(it) for _ in range(rep + 2)]
            if h["pack"] == "group":
                qg, kg, vg = grp[:rep], grp[rep], grp[rep + 1]
            else:  # group_kvfirst
                kg, vg, qg = grp[0], grp[1], grp[2:]
            k[g], v[g] = kg, vg
            for r in range(rep):
                idx = r * KV + g if h["head_order"] == "tile" else g * rep + r
                q[idx] = qg[r]
        return torch.stack(q).reshape(H * hd, *w.shape[1:]), torch.stack(k).reshape(KV * hd, *w.shape[1:]), \
            torch.stack(v).reshape(KV * hd, *w.shape[1:]), "grouped"

    def forward(self, ids, h):
        c, sd = self.c, self.sd
        H, KV, hd, d = c["n_heads"], c["n_kv_heads"], c["d_head"], c["d_model"]
        rep = H // KV
        rot = int(round(c["rotary"]["pct"] * hd))
        mup = c["mup"]
        t = ids.shape[1]
        den = hd if h["denom"] == "head" else rot
        rc = h.get("rope_cache", "inv_bf16")
        if rc == "none":
            idx = torch.arange(rot // 2, dtype=torch.float64)
            inv = 1.0 / (c["rotary"]["theta"] ** (2 * idx / den))
        else:
            idx = torch.arange(rot // 2, dtype=torch.float32)
            inv = 1.0 / (c["rotary"]["theta"] ** (2.0 * idx / den))
            inv = (inv.to(torch.bfloat16) if rc == "inv_bf16" else inv).to(torch.float64)
        pos = torch.arange(t, dtype=torch.float64) / c["rotary"]["interp_factor"]
        ang = torch.outer(pos, inv)
        cos, sin = ang.cos(), ang.sin()
        if rc == "cossin_bf16":
            cos, sin = cos.to(torch.bfloat16), sin.to(torch.bfloat16)
        cos, sin = cos.to(self.dtype), sin.to(self.dtype)
        sl = slice(0, rot) if h["rope_place"] == "first" else slice(hd - rot, hd)

        def rope(x):
            x = x.clone()
            xr = x[..., sl]
            if h["rope_layout"] == "half":
                a, b = xr[..., :rot // 2], xr[..., rot // 2:]
                out = torch.cat([a * cos - b * sin, b * cos + a * sin], -1)
            else:
                a, b = xr[..., 0::2], xr[..., 1::2]
                out = torch.stack([a * cos - b * sin, b * cos + a * sin], -1).flatten(-2)
            x[..., sl] = out
            return x

        temp = {"dhead": 1.0 / hd, "dmodel": 1.0 / d, "sqrt": hd ** -0.5}[h["attn_temp"]]
        x = sd["tok_emb.weight"][ids] * mup["input_alpha"]
        mask = torch.ones(t, t, dtype=torch.bool).tril()
        for i in range(c["n_layers"]):
            p = f"layers.{i}."
            y = F.layer_norm(x, (d,), sd[p + "ln1.weight"], sd[p + "ln1.bias"], c["norm_eps"])
            wq, wk, wv, kind = self.unpack_qkv(sd[p + "attn.wqkv.weight"], h)
            bq, bk, bv, _ = self.unpack_qkv(sd[p + "attn.wqkv.bias"], h)
            q = (y @ wq.T + bq).view(1, t, H, hd).transpose(1, 2)
            k = (y @ wk.T + bk).view(1, t, KV, hd).transpose(1, 2)
            v = (y @ wv.T + bv).view(1, t, KV, hd).transpose(1, 2)
            q, k = rope(q), rope(k)
            if kind == "flat" and h["head_order"] == "contig":
                k, v = k.repeat_interleave(rep, 1), v.repeat_interleave(rep, 1)
            else:
                # grouped packing already fixed which kv each q head reads (by idx); flat+tile tiles
                kv_of = [hh % KV for hh in range(H)] if (kind == "flat" or h["head_order"] == "tile") \
                    else [hh // rep for hh in range(H)]
                k, v = k[:, kv_of], v[:, kv_of]
            att = (q @ k.transpose(-1, -2)) * temp
            att = att.masked_fill(~mask, float("-inf")).softmax(-1)
            o = (att @ v).transpose(1, 2).reshape(1, t, H * hd)
            x = x + mup["residual_alpha"] * (o @ sd[p + "attn.wo.weight"].T + sd[p + "attn.wo.bias"])
            y = F.layer_norm(x, (d,), sd[p + "ln2.weight"], sd[p + "ln2.bias"], c["norm_eps"])
            z = y @ sd[p + "mlp.w_in.weight"].T + sd[p + "mlp.w_in.bias"]
            a, b = z.chunk(2, -1)
            up, gate = (a, b) if h["mlp"] == "up_gate" else (b, a)
            x = x + mup["residual_alpha"] * ((F.silu(gate) * up) @ sd[p + "mlp.w_out.weight"].T + sd[p + "mlp.w_out.bias"])
        x = F.layer_norm(x, (d,), sd["ln_f.weight"], None, c["norm_eps"])
        return (x @ sd["tok_emb.weight"].T) * mup["output_alpha"]
