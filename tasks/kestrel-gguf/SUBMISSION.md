# kestrel-gguf

- idea check pitch: an in-house PyTorch decoder (pre-LN LayerNorm with bias, biased SwiGLU, tiled-kv GQA, half-split partial RoPE with 0.5 position scale, muP multipliers, tied head) must run on stock llama.cpp b10964 with no patches; deliverable /app/kestrel.gguf (all F32), graded by running the real llama.cpp on 21 sealed texts: token ids must equal the HF tokenizer.json exactly and every log-softmax entry must be within 5e-3 nats of the float64 PyTorch reference. No llama.cpp graph fits natively, so the port needs exact weight algebra (residual centering to turn LayerNorm into RMSNorm, bias folding, head regrouping, channel interleave + rope_freqs).
- category: ML
- labels: Inference (primary), Kernels
- task name: kestrel-gguf
- zip: tasks/kestrel-gguf/kestrel-gguf.zip
