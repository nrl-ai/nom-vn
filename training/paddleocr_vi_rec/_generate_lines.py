"""Generate Vietnamese OCR rec training corpus — line-level images + labels.

Pulls VN sentences from the existing in-tree corpora (UDHR, wiki_vi,
tatoeba_vi, wikisource Truyện Kiều, plus the synthetic-content
templates from `benchmarks/data/vn_documents_ocr_v2/_business_templates`)
and renders each as a single-line image at a fixed height (48 px),
varied width, with mild scan artifacts. Output is in PaddleOCR rec
format:

    out/
      images/<id>.png      — line crop
      train_list.txt        — "images/<id>.png\\t<label>" per line
      val_list.txt          — same format
      vi_dict.txt           — one char per line, sorted

Each unique sentence is rendered N times with different fonts / scan
profiles / rotation so the model sees realistic variation.

Run from the repo root::

    python training/paddleocr_vi_rec/_generate_lines.py \\
        --output training/paddleocr_vi_rec/data \\
        --target-images 30000

Acceptance check on the output: `train_list.txt` has the expected line
count, every label is in NFC, and `vi_dict.txt` covers all chars seen
in labels.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "benchmarks" / "data" / "vn_documents_ocr_v2"))
sys.path.insert(0, str(Path(__file__).parent))

from _business_templates import (  # noqa: E402
    CONTRACT_GENERATORS,
    FORM_GENERATORS,
    RECEIPT_GENERATORS,
)
from _overlays import maybe_apply_overlay  # noqa: E402
from _scan_artifacts import ScanProfile  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

# Round-1 fonts (4) — DejaVu family
DEJAVU_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
DEJAVU_SERIF = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
DEJAVU_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")

# Round-3 fonts (4) — VN-tuned, OFL-licensed
_FONT_DIR = Path(__file__).parent / "fonts"
BE_VN_PRO = _FONT_DIR / "BeVietnamPro-Regular.ttf"
BITTER = _FONT_DIR / "Bitter[wght].ttf"
OPEN_SANS = _FONT_DIR / "OpenSans[wdth,wght].ttf"
ROBOTO = _FONT_DIR / "Roboto-Regular.ttf"

LINE_HEIGHT = 48
TARGET_FONT_PX = 32
MIN_WIDTH = 80
MAX_WIDTH = 1200


@dataclass(frozen=True, slots=True)
class LineSpec:
    """One line of training data — sentence text + render parameters."""

    text: str
    font_path: Path
    profile: ScanProfile
    italic: bool = False  # PIL doesn't synthesize italic; flag for future


def _wrap_punct(s: str) -> str:
    """Light cleanup — collapse multiple spaces, strip control chars."""
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"\s+", " ", s).strip()


def _split_sentences(text: str, *, min_chars: int = 8, max_chars: int = 90) -> list[str]:
    """Cut a paragraph into sentence-shaped fragments suitable for line OCR.

    Sentences too long for a 1200-px line get further split on punctuation.
    """
    text = _wrap_punct(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?:;])\s+", text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if len(p) < min_chars:
            continue
        if len(p) <= max_chars:
            out.append(p)
            continue
        # Long sentence — split further on commas / dashes
        for chunk in re.split(r"(?<=[,;—])\s+", p):
            chunk = chunk.strip()
            if min_chars <= len(chunk) <= max_chars:
                out.append(chunk)
    return out


# ---------- Source loaders ----------


def _load_wiki_extracts() -> list[str]:
    path = REPO / "benchmarks" / "data" / "wiki_vi" / "articles.jsonl"
    if not path.exists():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        for sent in _split_sentences(d.get("extract", "")):
            out.append(sent)
    return out


def _load_udhr() -> list[str]:
    path = REPO / "benchmarks" / "data" / "udhr_vi" / "udhr_vi.txt"
    if not path.exists():
        return []
    return _split_sentences(path.read_text(encoding="utf-8"))


def _load_tatoeba() -> list[str]:
    path = REPO / "benchmarks" / "data" / "tatoeba_vi" / "vie_sentences_sample_3k.tsv"
    if not path.exists():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        s = (parts[-1] if parts else "").strip()
        if 8 <= len(s) <= 200:
            out.extend(_split_sentences(s))
    return out


def _load_wikisource() -> list[str]:
    out: list[str] = []
    base = REPO / "benchmarks" / "data" / "wikisource_vi"
    for fn in ("bai_tua_truyen_kieu.txt", "tua_truyen_kieu.txt", "tong_vinh_truyen_kieu.txt"):
        p = base / fn
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        # Skip metadata noise lines (matching the synth_corpus filter)
        clean = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if re.match(r"^\d{4,7}[A-ZĐÀ-ỹ]", s):
                continue
            if s.startswith(("•", "▲", "Chú thích")):
                continue
            clean.append(s)
        out.extend(_split_sentences("\n".join(clean)))
    return out


def _load_business_template_lines() -> list[str]:
    """Pull individual lines from receipt/contract/form template outputs.

    Each template is invoked at 4 seeds; we split the body text into
    sentence-shaped fragments. Gives us realistic VN business document
    line content (numbers, IDs, addresses, amounts).
    """
    out: list[str] = []
    for gens in (RECEIPT_GENERATORS, CONTRACT_GENERATORS, FORM_GENERATORS):
        for gen in gens:
            for seed in range(4):
                try:
                    _title, body = gen(seed)
                except Exception:
                    continue
                # Split on newlines first (template structure), then sentences.
                for paragraph in body.split("\n\n"):
                    for line in paragraph.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        for sent in _split_sentences(line, min_chars=6, max_chars=120):
                            out.append(sent)
    return out


# ---------- Render ----------


def _render_line(text: str, font_path: Path, target_h: int = LINE_HEIGHT) -> Image.Image:
    """Render `text` as a single-line image at height `target_h`."""
    font = ImageFont.truetype(str(font_path), TARGET_FONT_PX)
    # Measure
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x = 12
    pad_y = (target_h - text_h) // 2
    img_w = max(MIN_WIDTH, min(MAX_WIDTH, text_w + 2 * pad_x))
    img = Image.new("RGB", (img_w, target_h), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((pad_x - bbox[0], pad_y - bbox[1]), text, fill="black", font=font)
    return img


def _augment_line(img: Image.Image, profile: ScanProfile, seed: int) -> Image.Image:
    """Light line-crop augmentation — JPEG round-trip + a touch of noise.

    PaddleOCR's `RecAug` already adds RandomColor / RandomCrop /
    affine perturbations during training, so the generator just needs
    to inject a realistic scan-noise floor. Skip the full 8-stage
    page-level pipeline (banding / vignette / edge bleed are
    page-scale phenomena and ~10x slower per image).
    """
    import io

    rng = random.Random(seed)
    # JPEG round-trip 78-92 quality
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=rng.randint(78, 92))
    buf.seek(0)
    return Image.open(buf).convert("RGB").copy()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / "training/paddleocr_vi_rec/data")
    parser.add_argument("--target-images", type=int, default=30000)
    parser.add_argument("--val-frac", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--multi-font",
        action="store_true",
        help="Use 8-font set (4 DejaVu + 4 VN-tuned). Default: 4 DejaVu only.",
    )
    parser.add_argument(
        "--overlay-prob",
        type=float,
        default=0.0,
        help="Probability of applying one stamp/signature/watermark overlay per crop. 0.0 = off (round-1 default); 0.30 = round-3 default.",
    )
    args = parser.parse_args()

    out_dir = args.output
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    print("Loading source sentences…", flush=True)
    sources: dict[str, list[str]] = {
        "wiki_vi": _load_wiki_extracts(),
        "udhr": _load_udhr(),
        "tatoeba": _load_tatoeba(),
        "wikisource": _load_wikisource(),
        "business_tpl": _load_business_template_lines(),
    }
    for name, lines in sources.items():
        print(f"  {name}: {len(lines)} sentences", flush=True)
    all_sentences = [s for src in sources.values() for s in src]
    # De-dup
    all_sentences = list(dict.fromkeys(all_sentences))
    print(f"Total unique sentences: {len(all_sentences)}", flush=True)

    if not all_sentences:
        print("error: no source sentences found", file=sys.stderr)
        return 1

    # Build the line specs by cycling through sentences with varied params.
    fonts: tuple[Path, ...] = (DEJAVU_REGULAR, DEJAVU_BOLD, DEJAVU_SERIF, DEJAVU_MONO)
    if args.multi_font:
        round3_fonts = tuple(p for p in (BE_VN_PRO, BITTER, OPEN_SANS, ROBOTO) if p.exists())
        fonts = fonts + round3_fonts
        print(f"Multi-font mode: {len(fonts)} fonts available", flush=True)
    profiles = list(ScanProfile)
    specs: list[LineSpec] = []
    while len(specs) < args.target_images:
        for sent in all_sentences:
            specs.append(
                LineSpec(
                    text=sent,
                    font_path=fonts[rng.randrange(len(fonts))],
                    profile=profiles[rng.randrange(len(profiles))],
                )
            )
            if len(specs) >= args.target_images:
                break
    rng.shuffle(specs)

    # Render
    print(f"Rendering {len(specs)} line crops…", flush=True)
    train_lines: list[str] = []
    val_lines: list[str] = []
    char_set: set[str] = set()
    val_threshold = int(len(specs) * (1 - args.val_frac))
    for i, spec in enumerate(specs):
        try:
            img = _render_line(spec.text, spec.font_path)
            img = _augment_line(img, spec.profile, seed=i)
            if args.overlay_prob > 0:
                img = maybe_apply_overlay(img, seed=i + 7919, prob=args.overlay_prob)
        except Exception as exc:
            print(f"  skip {i} ({spec.text[:40]!r}): {exc}", file=sys.stderr)
            continue
        out_path = img_dir / f"{i:08d}.png"
        img.save(out_path, format="PNG", optimize=True)
        line = f"images/{out_path.name}\t{spec.text}\n"
        if i < val_threshold:
            train_lines.append(line)
        else:
            val_lines.append(line)
        char_set.update(spec.text)
        if (i + 1) % 2000 == 0:
            print(f"  {i + 1} / {len(specs)}", flush=True)

    (out_dir / "train_list.txt").write_text("".join(train_lines), encoding="utf-8")
    (out_dir / "val_list.txt").write_text("".join(val_lines), encoding="utf-8")

    # Build dictionary — every distinct char in labels, sorted by codepoint.
    dict_chars = sorted(c for c in char_set if c not in ("\t", "\n"))
    (out_dir / "vi_dict.txt").write_text("\n".join(dict_chars) + "\n", encoding="utf-8")

    print(f"\nGenerated {len(train_lines)} train + {len(val_lines)} val crops")
    print(f"  Dictionary size: {len(dict_chars)} chars")
    print(f"  Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
