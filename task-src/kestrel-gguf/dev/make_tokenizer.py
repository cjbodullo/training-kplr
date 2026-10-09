"""train the kestrel byte level bpe tokenizer (dev only)."""
import glob
import os
import sys

from tokenizers import Regex, Tokenizer, decoders, models, pre_tokenizers, processors, trainers

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "kestrel", "tokenizer.json")

SPLIT = (r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}"
         r"| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+")

tok = Tokenizer(models.BPE(byte_fallback=False, ignore_merges=False))
tok.pre_tokenizer = pre_tokenizers.Sequence([
    pre_tokenizers.Split(Regex(SPLIT), behavior="isolated", invert=False),
    pre_tokenizers.ByteLevel(add_prefix_space=False, trim_offsets=False, use_regex=False),
])
tok.decoder = decoders.ByteLevel(add_prefix_space=False, trim_offsets=False, use_regex=False)
specials = ["<|pad|>", "<|bos|>", "<|eos|>"]
trainer = trainers.BpeTrainer(
    vocab_size=4096,
    min_frequency=2,
    special_tokens=specials,
    initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
    show_progress=False,
)
files = sorted(glob.glob(os.path.join(HERE, "corpus", "*.txt")))
tok.train(files, trainer)
tok.post_processor = processors.TemplateProcessing(
    single="<|bos|> $A",
    pair="<|bos|> $A <|bos|> $B",
    special_tokens=[("<|bos|>", tok.token_to_id("<|bos|>"))],
)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tok.save(OUT)
print("vocab", tok.get_vocab_size(), "->", OUT)
print(tok.encode("Hello world, it's 2026-10-08 and 12345 apples.").tokens)
