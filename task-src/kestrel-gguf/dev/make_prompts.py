"""build candidate held out prompts (dev only). each is cut to a target token count with the
kestrel tokenizer (bos included). final selection happens after the reference gguf is checked."""
import glob
import json
import os
import random
import sys

from tokenizers import Tokenizer

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "prompts_candidates")
tok = Tokenizer.from_file(os.path.join(HERE, "kestrel", "tokenizer.json"))
rng = random.Random(77123)
LCPP = os.environ.get("LCPP", "/opt/llama.cpp")
os.makedirs(OUT, exist_ok=True)


def ntok(s):
    return len(tok.encode(s).ids)


def body(path):
    t = open(path, encoding="utf-8").read()
    a = t.find("*** START OF")
    b = t.find("*** END OF")
    t = t[a:b] if a >= 0 and b > a else t
    return t[t.find("\n", 0) + 1:]


def cut(text, target, start=None):
    """take a window of text starting near start whose token count is <= target, as long as possible."""
    if start is None:
        start = rng.randrange(0, max(1, len(text) - 40 * target))
    lo, hi = 1, min(len(text) - start, 40 * target)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ntok(text[start:start + mid]) <= target:
            lo = mid
        else:
            hi = mid - 1
    return text[start:start + lo]


prompts = {}
H = os.path.join(HERE, "heldout")
prompts["dracula"] = cut(body(f"{H}/pg345.txt"), 1900)
prompts["ulysses"] = cut(body(f"{H}/pg4300.txt"), 1500)
prompts["trial"] = cut(body(f"{H}/pg7849.txt"), 800)
prompts["wallpaper"] = cut(body(f"{H}/pg1952.txt"), 400)
prompts["crime_max"] = cut(body(f"{H}/pg2554.txt"), 2048)
prompts["quijote"] = cut(body(f"{H}/pg2000.txt"), 1200)
prompts["sanguo"] = cut(body(f"{H}/pg23950.txt"), 700)

# source code
torch_dir = os.path.dirname(__import__("torch").__file__)
py = open(os.path.join(torch_dir, "nn", "modules", "conv.py"), encoding="utf-8").read()
prompts["python_src"] = cut(py, 1500, start=py.find("class _ConvNd"))
c_src = open(os.path.join(LCPP, "ggml/src/ggml-cpu/ops.cpp"), encoding="utf-8").read()
prompts["cpp_src"] = cut(c_src, 1000, start=c_src.find("static void ggml_compute_forward_rope_flt"))

# numbers
lines = []
t = 1759900000
for i in range(400):
    t += rng.randint(1, 900)
    ip = ".".join(str(rng.randint(1, 254)) for _ in range(4))
    lat = rng.random() * 3000
    lines.append(f"2025-10-{8 + i // 150:02d}T{(t // 3600) % 24:02d}:{(t // 60) % 60:02d}:{t % 60:02d}.{rng.randint(0, 999999):06d}Z "
                 f"{ip} GET /api/v2/orders/{rng.randint(10000, 99999999)} {rng.choice([200, 200, 201, 304, 404, 500])} "
                 f"{lat:.3f}ms bytes={rng.randint(0, 10 ** rng.randint(1, 9))}")
prompts["access_log"] = cut("\n".join(lines), 1200, start=0)
rows = ["sku,warehouse,qty,unit_price_eur,updated"]
for i in range(300):
    rows.append(f"{rng.randint(100000, 999999)}-{rng.choice('ABCDEFG')}{rng.randint(0, 99):02d},WH{rng.randint(1, 40)},"
                f"{rng.randint(0, 12000)},{rng.randint(0, 99999) / 100:.2f},2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}")
prompts["csv_table"] = cut("\n".join(rows), 900, start=0)
digits = "3." + "".join(str(rng.randint(0, 9)) for _ in range(3000))
prompts["digit_run"] = cut(digits, 1600, start=0)
obj = {"id": "a7f3", "items": [{"name": rng.choice(["Ünïcode", "naïve café", "Smörgåsbord", "plain"]),
                                "price": round(rng.random() * 1000, 4), "tags": ["x", "y"] * rng.randint(0, 2),
                                "ok": rng.random() < 0.5, "n": rng.randint(-10 ** 6, 10 ** 6)} for _ in range(60)]}
prompts["json_blob"] = cut(json.dumps(obj, indent=2, ensure_ascii=False), 700, start=0)

# scripts and symbols
mixed = (
    "Ελληνικά: Η γρήγορη καφέ αλεπού πηδάει πάνω από τον τεμπέλη σκύλο.\n"
    "Русский: Съешь же ещё этих мягких французских булок, да выпей чаю.\n"
    "日本語：いろはにほへと ちりぬるを わかよたれそ つねならむ。東京は2024年に3,750万人。\n"
    "中文：我们在2025年10月8日发布了第3版，共有１２３４５个测试。\n"
    "한국어: 다람쥐 헌 쳇바퀴에 타고파. 가격은 ₩12,900 입니다.\n"
    "العربية: نص حكيم له سر قاطع وذو شأن عظيم مكتوب على ثوب أخضر ١٢٣٤٥\n"
    "हिन्दी: ऋषियों को सताने वाले दुष्ट राक्षसों के राजा रावण का सर्वनाश करने वाले विष्णुवतार भगवान श्रीराम।\n"
    "Emoji: 👩‍💻 deployed 🚀 at 03:14 — 🎉🎉 ok? 👍🏽 ❤️ 🇩🇪 🏳️‍🌈\n"
    "Math: ∀x∈ℝ, ∑ᵢ₌₁ⁿ xᵢ² ≥ 0 ⇒ √(x²) = |x|; ∫₀^∞ e^(−x²) dx = √π/2 ≈ 0.8862269254\n"
    "Combining: é vs é, ñ, Å, ﬁ ligature, ｆｕｌｌｗｉｄｔｈ ＡＢＣ １２３\n"
    "Zero width: a​b‌c‍d ﻿BOM nbsp thin　ideographic\n"
    "Superscripts: x² y³ ½ ¾ ⅞ Ⅻ ⑦ ⁸ ₉ 𝟘𝟙𝟚 𝔘𝔫𝔦𝔠𝔬𝔡𝔢\n"
)
prompts["mixed_scripts"] = mixed
ws = []
for i in range(80):
    ws.append(rng.choice(["\t", "    ", "  ", "", "\t\t"]) + rng.choice(["if x:", "return  y", "a\t=\tb", "# note   ", "   ", "x = [1,  2,   3]"])
              + rng.choice(["", " ", "  ", "\t"]) + rng.choice(["\n", "\r\n", "\n\n", "\r\n\r\n", "\n   \n"]))
prompts["whitespace"] = cut("".join(ws), 700, start=0)
prompts["shouting"] = ("DON'T YOU DARE. I'LL SAY IT AGAIN: WE'RE NOT DONE, THEY'VE GOT TO STOP. SHE'D KNOW. IT'S MINE.\n"
                       "don't Don't DON'T dOn'T we'Ll they'Re I'M you'D ’tis rock'n'roll O'Neil's 'quoted' ''double''\n") * 6
prompts["hello"] = "Hi"
prompts["one_digit"] = "7"
prompts["empty"] = ""
prompts["emoji_only"] = "🙂"
prompts["markdown"] = cut(open(os.path.join(LCPP, "README.md"), encoding="utf-8").read(), 1100, start=0)

for k, v in prompts.items():
    with open(os.path.join(OUT, k + ".txt"), "w", encoding="utf-8", newline="") as f:
        f.write(v)
    print(f"{k:14s} {ntok(v):5d} tokens {len(v):6d} chars")
