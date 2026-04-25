"""Sample a real VN OCR bench fixture from ducto489/ocr_datasets.

Source: https://huggingface.co/datasets/ducto489/ocr_datasets
License: Apache-2.0 (per dataset card, fetched 2026-04-25)
Origin: aggregated VN OCR images from the vietocr training corpus, plus
   English OCR images. We keep only Vietnamese rows by diacritic filter.

Output (under ``benchmarks/data/vn_ocr_subset/``):

  ground_truth.jsonl   — one line per sample: {"id", "text", "image"}
  images/              — 500 PNGs sampled deterministically (seed=42)

Tiny + redistributable + Apache 2.0 → safe to ship in the bench HF dataset.

Run::

    python benchmarks/data/vn_ocr_subset/_build.py
    python benchmarks/data/vn_ocr_subset/_build.py --n 200 --seed 7
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent

VN_CHARS = set(
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
)


def _has_vn(text: str) -> bool:
    return any(c in VN_CHARS for c in (text or ""))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--shard",
        default="default/partial-train/0000.parquet",
        help="Path within the parquet revision of ducto489/ocr_datasets.",
    )
    p.add_argument(
        "--min-len",
        type=int,
        default=8,
        help="Skip ground-truth strings shorter than this many chars (filters single-word noise).",
    )
    args = p.parse_args(argv)

    try:
        import pandas as pd
        from huggingface_hub import hf_hub_download
        from PIL import Image
    except ImportError as exc:
        print(
            f"missing dep: {exc}. pip install datasets pandas pillow huggingface_hub",
            file=sys.stderr,
        )
        return 2

    print(f"downloading shard {args.shard}...")
    shard = hf_hub_download(
        repo_id="ducto489/ocr_datasets",
        filename=args.shard,
        repo_type="dataset",
        revision="refs/convert/parquet",
    )
    df = pd.read_parquet(shard)
    print(f"  {len(df)} total rows")

    # Filter: VN-bearing text, min length
    df = df[df["txt"].fillna("").map(lambda s: _has_vn(s) and len(s) >= args.min_len)]
    print(f"  {len(df)} after VN + min-len filter")

    # Deterministic sample
    rng = random.Random(args.seed)
    indices = list(range(len(df)))
    rng.shuffle(indices)
    indices = indices[: args.n]

    images_dir = OUT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    gt_path = OUT / "ground_truth.jsonl"

    written = 0
    with gt_path.open("w", encoding="utf-8") as gf:
        for new_id, idx in enumerate(indices):
            row = df.iloc[idx]
            jpg_field = row["jpg"]
            # Parquet writer encodes bytes either as raw bytes or {"bytes": ..., "path": ...}
            if isinstance(jpg_field, dict):
                raw = jpg_field.get("bytes") or jpg_field.get("data")
            else:
                raw = jpg_field
            if not raw:
                continue
            try:
                img = Image.open(io.BytesIO(raw)).convert("RGB")
            except Exception as exc:
                print(f"  skip {idx}: image decode failed ({exc})")
                continue
            out_path = images_dir / f"{new_id:04d}.png"
            img.save(out_path, format="PNG")
            gf.write(
                json.dumps(
                    {
                        "id": f"{new_id:04d}",
                        "text": row["txt"],
                        "image": f"images/{new_id:04d}.png",
                        "source_key": row["__key__"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            written += 1

    print(f"→ wrote {written} samples to {OUT}")
    print(f"  ground truth: {gt_path}")
    print(f"  images dir:   {images_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
