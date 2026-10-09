`/app/kestrel` holds a small decoder we trained in house, kestrel. `modeling_kestrel.py` is plain torch and it is the source of truth for the math. next to it are `config.json`, `model.safetensors` and the tokenizer as a hugging face `tokenizer.json` (tokenizers 0.21.1). it never went through transformers and it is not an arch llama.cpp knows.

i need `/app/kestrel.gguf` that runs on the exact llama.cpp we ship on device, tag `b10964` (the build in `/opt/llama.cpp`). we can't patch llama.cpp or add an arch to it. device build is stock and grading uses its own clean build of the same tag. so the gguf has to say everything by itself.

how i check it. harness is `/usr/local/bin/kestrel-logits`, source in `/opt/kestrel-eval/kestrel_logits.cpp`. read it, the settings in there are what we use: cpu, n_ctx 2048, f32 kv cache, no flash attn, whole prompt in one batch, bos added if the gguf asks for it. i run it over a set of held out utf8 texts you don't get. prose in a few languages, source code, logs and tables full of numbers, mixed scripts and emoji, whitespace heavy stuff, a couple of tiny ones. anything from empty up to 2048 tokens counting bos. for every text two things must hold. token ids from llama.cpp equal `tokenizer.json` encode of that text (with its post processor, so bos first) exactly. and at every position the log softmax of llama.cpp logits is within 0.005 nats of what `modeling_kestrel.py` gives in float64, for every one of the 4096 vocab entries. one text off and the whole thing fails.

keep every tensor in the gguf f32. quantizing is a later job and i want a clean baseline first. file under 256 MiB.

honestly the bit i care about is that this is the real model on llama.cpp, not something close. close is what we had last time.

You have 18000 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
