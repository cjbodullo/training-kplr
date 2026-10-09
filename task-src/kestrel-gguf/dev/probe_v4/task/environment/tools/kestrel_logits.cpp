// kestrel-logits: run a gguf through stock libllama on one utf-8 text file and dump
// the token ids and the logits of every position.
//
//   kestrel-logits <model.gguf> <text.txt> <out.bin>
//
// settings are fixed: cpu only, n_ctx 2048, one batch for the whole prompt, f32 kv cache,
// flash attention off, add_special=true (bos if the gguf asks for it), parse_special=false.
// out.bin: int32 n_tokens, int32 n_vocab, int32 ids[n_tokens], float32 logits[n_tokens][n_vocab]

#include "llama.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

static void quiet_log(ggml_log_level level, const char * text, void *) {
    if (level >= GGML_LOG_LEVEL_ERROR || getenv("KESTREL_LOGITS_VERBOSE")) {
        fputs(text, stderr);
    }
}

int main(int argc, char ** argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s <model.gguf> <text.txt> <out.bin>\n", argv[0]);
        return 2;
    }
    const int n_ctx = 2048;

    std::ifstream in(argv[2], std::ios::binary);
    if (!in) { fprintf(stderr, "cannot read %s\n", argv[2]); return 2; }
    std::stringstream ss; ss << in.rdbuf();
    const std::string text = ss.str();

    llama_log_set(quiet_log, nullptr);
    llama_backend_init();

    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;
    llama_model * model = llama_model_load_from_file(argv[1], mp);
    if (!model) { fprintf(stderr, "failed to load model\n"); return 3; }
    const llama_vocab * vocab = llama_model_get_vocab(model);
    const int n_vocab = llama_vocab_n_tokens(vocab);

    std::vector<llama_token> toks(text.size() + 8);
    int n = llama_tokenize(vocab, text.data(), (int) text.size(), toks.data(), (int) toks.size(), true, false);
    if (n < 0) { fprintf(stderr, "tokenize failed\n"); return 4; }
    toks.resize(n);
    if (n == 0 || n > n_ctx) { fprintf(stderr, "prompt has %d tokens, need 1..%d\n", n, n_ctx); return 4; }

    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = n_ctx;
    cp.n_batch = n_ctx;
    cp.n_ubatch = n_ctx;
    cp.n_seq_max = 1;
    cp.n_threads = 4;
    cp.n_threads_batch = 4;
    cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
    cp.type_k = GGML_TYPE_F32;
    cp.type_v = GGML_TYPE_F32;
    cp.no_perf = true;
    llama_context * ctx = llama_init_from_model(model, cp);
    if (!ctx) { fprintf(stderr, "failed to create context\n"); return 3; }

    llama_batch batch = llama_batch_init(n, 0, 1);
    for (int i = 0; i < n; ++i) {
        batch.token[i] = toks[i];
        batch.pos[i] = i;
        batch.n_seq_id[i] = 1;
        batch.seq_id[i][0] = 0;
        batch.logits[i] = 1;
    }
    batch.n_tokens = n;
    if (llama_decode(ctx, batch) != 0) { fprintf(stderr, "decode failed\n"); return 5; }

    FILE * out = fopen(argv[3], "wb");
    if (!out) { fprintf(stderr, "cannot write %s\n", argv[3]); return 2; }
    int32_t hdr[2] = { n, n_vocab };
    fwrite(hdr, sizeof(int32_t), 2, out);
    fwrite(toks.data(), sizeof(int32_t), n, out);
    for (int i = 0; i < n; ++i) {
        const float * lg = llama_get_logits_ith(ctx, i);
        if (!lg) { fprintf(stderr, "no logits at %d\n", i); return 5; }
        fwrite(lg, sizeof(float), n_vocab, out);
    }
    fclose(out);

    llama_batch_free(batch);
    llama_free(ctx);
    llama_model_free(model);
    llama_backend_free();
    return 0;
}
