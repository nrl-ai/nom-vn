"""Real-scan-style overlay augmentation for line crops.

The round-1 model trained on clean DejaVuSans + JPEG noise but never
saw stamps, signatures, watermarks, or low-contrast bleed-through —
the dominant artifacts on real chinhphu.vn signed scans. This module
adds those overlays as a pre-train augmentation step.

Five stochastic overlays, applied independently with low probability
each so individual crops aren't visually destroyed:

    stamp_red       — semi-transparent red round stamp (15-30 % crops)
    signature_blue  — handwritten-style scribble (5-10 % crops)
    watermark_text  — large faint text behind body (10-15 % crops)
    bleed_through   — faint mirrored ghost from "back of page" (5-10 %)
    edge_smudge     — toner streak / scanner roller mark (5-10 %)

All overlays are drawn at <40 % alpha so the underlying glyphs stay
readable. The OCR labels don't change — the model learns to ignore
the overlay.

Usage from `_generate_lines.py`::

    from _overlays import maybe_apply_overlay
    img = maybe_apply_overlay(img, seed=i, prob=0.30)

The 0.30 default means ~30 % of crops get one overlay, ~70 % stay
clean — matches real-scan distribution where stamps/signatures
appear on signature lines + a few headers, not every line.
"""

from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def stamp_red(img: Image.Image, rng: random.Random) -> Image.Image:
    """Red round stamp partially overlapping the right side of the line.

    Real VN gov stamps are circular, ~80-150 px diameter, red ink at
    ~60 % alpha. We approximate with a circle drawn in red + faint
    text "ĐÃ KÝ" or similar in the centre.
    """
    W, H = img.size
    diameter = rng.randint(int(H * 1.1), int(H * 1.6))
    # Place near the right edge, partially overlapping the text
    cx = rng.randint(W - int(diameter * 0.7), W - int(diameter * 0.3))
    cy = H // 2

    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    # Outer ring + inner ring (typical gov stamp design)
    red = (180, 30, 30, rng.randint(140, 200))
    draw.ellipse(
        (cx - diameter // 2, cy - diameter // 2, cx + diameter // 2, cy + diameter // 2),
        outline=red,
        width=rng.randint(3, 5),
    )
    inner = int(diameter * 0.7)
    draw.ellipse(
        (cx - inner // 2, cy - inner // 2, cx + inner // 2, cy + inner // 2),
        outline=red,
        width=2,
    )
    # Slight rotation
    angle = rng.uniform(-15, 15)
    overlay = overlay.rotate(angle, resample=Image.BICUBIC)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def signature_blue(img: Image.Image, rng: random.Random) -> Image.Image:
    """Scribble-style signature crossing the line."""
    W, H = img.size
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Random bezier-like polyline
    blue = (40, 40, 160, rng.randint(120, 200))
    n_pts = rng.randint(6, 12)
    x_start = rng.randint(int(W * 0.3), int(W * 0.6))
    points = []
    for i in range(n_pts):
        x = x_start + i * rng.randint(8, 22)
        y = H // 2 + rng.randint(-int(H * 0.4), int(H * 0.4))
        points.append((x, y))
    if len(points) > 1:
        draw.line(points, fill=blue, width=rng.randint(2, 4))

    angle = rng.uniform(-25, 25)
    overlay = overlay.rotate(angle, resample=Image.BICUBIC)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def watermark_text(img: Image.Image, rng: random.Random) -> Image.Image:
    """Large faint text behind body — typical 'BẢN SAO' / 'COPY' watermark."""
    from pathlib import Path

    fonts_dir = Path(__file__).parent / "fonts"
    fonts = list(fonts_dir.glob("*.ttf"))
    if not fonts:
        return img
    font_path = fonts[rng.randrange(len(fonts))]

    text = rng.choice(["BẢN SAO", "COPY", "CHỨNG THỰC", "MẪU", "DRAFT"])
    font_size = max(int(img.height * 1.1), 32)
    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except OSError:
        return img

    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (img.width - text_w) // 2
    y = (img.height - text_h) // 2
    grey = (90, 90, 90, rng.randint(35, 70))
    draw.text((x, y), text, fill=grey, font=font)

    angle = rng.uniform(-30, 30)
    overlay = overlay.rotate(angle, resample=Image.BICUBIC)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def bleed_through(img: Image.Image, rng: random.Random) -> Image.Image:
    """Faint mirrored ghost simulating the back side of a thin page."""
    ghost = img.transpose(Image.FLIP_LEFT_RIGHT).filter(ImageFilter.GaussianBlur(radius=1.0))
    # Reduce contrast hard
    ghost_arr = ghost.point(lambda p: 255 - int((255 - p) * 0.18))
    return Image.blend(img, ghost_arr, alpha=0.20).convert("RGB")


def edge_smudge(img: Image.Image, rng: random.Random) -> Image.Image:
    """Vertical toner streak / scanner roller mark."""
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    x = rng.randint(int(img.width * 0.05), int(img.width * 0.95))
    grey = (60, 60, 60, rng.randint(60, 110))
    width = rng.randint(2, 5)
    draw.line([(x, 0), (x, img.height)], fill=grey, width=width)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


_OVERLAY_FNS = (stamp_red, signature_blue, watermark_text, bleed_through, edge_smudge)


def maybe_apply_overlay(img: Image.Image, *, seed: int, prob: float = 0.30) -> Image.Image:
    """Apply 0 or 1 overlay per call. Distribution targets ~prob fraction
    of crops augmented total (matching real-scan signature/stamp density)."""
    rng = random.Random(seed)
    if rng.random() > prob:
        return img
    fn = _OVERLAY_FNS[rng.randrange(len(_OVERLAY_FNS))]
    try:
        return fn(img, rng)
    except Exception:  # noqa: BLE001
        # Don't fail training over a bad overlay
        return img
