"""Render Vietnamese sentences from the CC0 diacritic-eval set as PNG images.

Output is CC0 (we generate it from CC0 input). Used for OCR smoke-testing
nom.doc image pipelines with perfect ground truth.

Run from repo root:

    python benchmarks/data/synthetic_ocr_vi/render.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
EVAL_TXT = ROOT.parent / "diacritic_eval_v0.txt"

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Medium.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
]


def load_sentences() -> list[str]:
    out = []
    for line in EVAL_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def render_clean(text: str, font_path: str, size: int = 28, pad: int = 24) -> Image.Image:
    font = ImageFont.truetype(font_path, size)
    bbox = font.getbbox(text)
    w, h = bbox[2] - bbox[0] + 2 * pad, bbox[3] - bbox[1] + 2 * pad
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.text((pad - bbox[0], pad - bbox[1]), text, fill="black", font=font)
    return img


def render_noisy(text: str, font_path: str, seed: int) -> Image.Image:
    rng = random.Random(seed)
    img = render_clean(text, font_path, size=rng.choice([22, 26, 30]))
    if rng.random() < 0.5:
        img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    if rng.random() < 0.5:
        # Light salt-and-pepper noise on the background
        px = img.load()
        w, h = img.size
        for _ in range(int(w * h * 0.005)):
            x, y = rng.randrange(w), rng.randrange(h)
            px[x, y] = (rng.randrange(50), rng.randrange(50), rng.randrange(50))
    if rng.random() < 0.4:
        img = img.rotate(rng.uniform(-2.0, 2.0), fillcolor="white", resample=Image.BILINEAR)
    return img


def main() -> None:
    sentences = load_sentences()
    rng = random.Random(2026)
    picks = rng.sample(sentences, k=min(20, len(sentences)))

    clean_dir = ROOT / "clean"
    noisy_dir = ROOT / "noisy"
    clean_dir.mkdir(exist_ok=True)
    noisy_dir.mkdir(exist_ok=True)

    truth = []
    for i, s in enumerate(picks):
        font = FONTS[i % len(FONTS)]
        clean = render_clean(s, font)
        clean_path = clean_dir / f"{i:03d}.png"
        clean.save(clean_path, "PNG", optimize=True)

        noisy = render_noisy(s, font, seed=i)
        noisy_path = noisy_dir / f"{i:03d}.png"
        noisy.save(noisy_path, "PNG", optimize=True)

        truth.append(
            {
                "id": f"{i:03d}",
                "text": s,
                "font": Path(font).name,
                "clean": str(clean_path.relative_to(ROOT)),
                "noisy": str(noisy_path.relative_to(ROOT)),
            }
        )

    (ROOT / "ground_truth.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in truth) + "\n", encoding="utf-8"
    )
    print(f"Rendered {len(truth)} clean + {len(truth)} noisy → ground_truth.jsonl")


if __name__ == "__main__":
    main()
