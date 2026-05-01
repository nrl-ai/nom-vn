"""Render Vietnamese sentences as **hard** OCR test images.

The existing `render.py` produces ``clean/`` (Tesseract `vie` ≈ 0 % CER)
and ``noisy/`` (Tesseract ≈ 0.7 % CER) — both in the diminishing-returns
band where post-OCR correction can't show value (every published
ByT5 / T5 post-correction paper warns about over-correcting at <2 %
baseline CER).

This script produces a third tier ``hard/`` that targets **5-15 % CER**
on Tesseract `vie`, which is where the literature says spell-correction
post-processing yields measurable improvements
([Löfgren & Dannélls 2024](https://aclanthology.org/2024.latechclfl-1.23/),
[Soper et al. 2023](https://arxiv.org/html/2309.11549)).

Augmentations applied (deterministic via per-image seed):

  * Smaller font (16-20 px instead of 22-30) to reduce per-glyph pixels
  * Heavier Gaussian blur (radius 1.0-1.6)
  * JPEG round-trip at quality 30-50 to add compression artefacts
  * Downsample-then-upsample (0.5x scale round-trip) to soften edges
  * Stronger salt-and-pepper noise (~3 % of pixels)
  * Random rotation ±3°
  * Background tint to simulate yellowed paper
  * Optional motion blur kernel for ~30 % of images

Output:
    benchmarks/data/synthetic_ocr_vi/hard/<id>.png
    benchmarks/data/synthetic_ocr_vi/ground_truth_hard.jsonl

Run from repo root:

    python benchmarks/data/synthetic_ocr_vi/render_hard.py
    python benchmarks/data/synthetic_ocr_vi/render_hard.py --n 50
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
EVAL_TXT = ROOT.parent / "diacritic_eval_v0.txt"

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Medium.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
]


def _load_sentences() -> list[str]:
    out: list[str] = []
    for line in EVAL_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def _render_text(text: str, font_path: str, size: int, pad: int = 18) -> Image.Image:
    font = ImageFont.truetype(font_path, size)
    bbox = font.getbbox(text)
    w, h = bbox[2] - bbox[0] + 2 * pad, bbox[3] - bbox[1] + 2 * pad
    img = Image.new("RGB", (w, h), (252, 248, 235))  # yellowed paper tint
    d = ImageDraw.Draw(img)
    d.text((pad - bbox[0], pad - bbox[1]), text, fill=(20, 20, 20), font=font)
    return img


def _degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    # 1. Heavy Gaussian blur
    img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(1.0, 1.6)))

    # 2. Downsample then upsample to soften edges
    w, h = img.size
    scale = rng.uniform(0.45, 0.6)
    img = img.resize((int(w * scale), int(h * scale)), Image.BILINEAR).resize(
        (w, h), Image.BILINEAR
    )

    # 3. Light contrast reduction
    img = ImageOps.autocontrast(img, cutoff=12)

    # 4. JPEG round-trip
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=rng.randint(30, 50))
    buf.seek(0)
    img = Image.open(buf).convert("RGB")

    # 5. Salt-and-pepper noise (~3 % of pixels)
    px = img.load()
    w, h = img.size
    n_noise = int(w * h * 0.03)
    for _ in range(n_noise):
        x, y = rng.randrange(w), rng.randrange(h)
        if rng.random() < 0.5:
            px[x, y] = (rng.randrange(40), rng.randrange(40), rng.randrange(40))
        else:
            px[x, y] = (rng.randrange(220, 256), rng.randrange(220, 256), rng.randrange(220, 256))

    # 6. Rotation
    img = img.rotate(rng.uniform(-3.0, 3.0), fillcolor=(252, 248, 235), resample=Image.BILINEAR)

    # 7. Optional motion-blur kernel (~30 % chance)
    if rng.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(radius=0.8))

    return img


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=30, help="Number of images to render.")
    p.add_argument("--seed", type=int, default=2026)
    args = p.parse_args()

    sentences = _load_sentences()
    rng = random.Random(args.seed)
    picks = rng.sample(sentences, k=min(args.n, len(sentences)))

    out_dir = ROOT / "hard"
    out_dir.mkdir(exist_ok=True)

    truth: list[dict] = []
    for i, s in enumerate(picks):
        font = FONTS[i % len(FONTS)]
        size = rng.choice([16, 18, 20])
        clean = _render_text(s, font, size=size)
        hard = _degrade(clean, random.Random(args.seed * 31 + i))

        img_id = f"{i:03d}"
        out_path = out_dir / f"{img_id}.png"
        hard.save(out_path)

        truth.append(
            {
                "id": img_id,
                "text": s,
                "font": Path(font).name,
                "font_size": size,
                "image": f"hard/{img_id}.png",
            }
        )

    truth_path = ROOT / "ground_truth_hard.jsonl"
    with truth_path.open("w", encoding="utf-8") as f:
        for r in truth:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"wrote {len(truth)} hard-OCR images to {out_dir}/")
    print(f"wrote ground truth to {truth_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
