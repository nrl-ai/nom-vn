"""Bench Tesseract + spell-correction post-processing on **real** VN OCR.

Companion to ``bench_ocr_post_correct.py`` (which used the synthetic
``synthetic_ocr_vi/hard`` test bed). This one uses
[`brianhuster/VietnameseOCRdataset`](https://huggingface.co/datasets/brianhuster/VietnameseOCRdataset)
— ~7,300 line-level Vietnamese handwriting images with ground truth.
Apache 2.0, license-clean.

Same metric definitions (NFC + Levenshtein-based CER + WER); same
post-correct pipeline (Tesseract → vn-spell-correction-base).

The handwriting register is fundamentally harder than printed text:
Tesseract `vie` baseline CER is expected in the 30-60 % band, where
literature ([Tran et al. 2024](https://arxiv.org/html/2410.13305))
reports the largest post-correct gains. This bench exists to find
out whether our shipped spell-correction model, trained on synthetic
typing-style noise, transfers to real handwriting OCR errors.

Usage::

    python scripts/fetch_brianhuster_ocr.py    # one-time setup
    python benchmarks/accuracy/bench_ocr_post_correct_real.py \\
        --json benchmarks/results/baseline_ocr_post_correct_real.json
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "benchmarks" / "accuracy"))
from bench_ocr_post_correct import _cer, _wer  # noqa: E402


def _load_annotations(path: Path) -> list[tuple[str, str]]:
    """Read TAB-separated annotation file: <relative_image_path>\\t<text>."""
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        img_path, text = parts
        rows.append((img_path.strip(), unicodedata.normalize("NFC", text.strip())))
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-root",
        type=Path,
        default=Path("/tmp/brianhuster_ocr/data_line"),
        help="Path to the extracted dataset_small.zip dir.",
    )
    p.add_argument(
        "--corrector",
        default="nrl-ai/vn-spell-correction-base",
        help="HF repo id of the post-correct model.",
    )
    p.add_argument("--n-samples", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--json", type=Path, default=None)
    p.add_argument("--examples", type=int, default=5)
    args = p.parse_args()

    annotations = _load_annotations(args.data_root / "test_line_annotation.txt")
    if not annotations:
        print(f"no annotations found under {args.data_root}", file=sys.stderr)
        return 2
    print(f"loaded {len(annotations)} test annotations")

    rng = random.Random(args.seed)
    samples = rng.sample(annotations, k=min(args.n_samples, len(annotations)))
    print(f"sampled {len(samples)} for bench (seed={args.seed})")

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        print(f"missing dep: {exc}", file=sys.stderr)
        return 2

    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    print(f"loading corrector {args.corrector}...")
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(args.corrector)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForSeq2SeqLM.from_pretrained(args.corrector).to(device).eval()
    print(f"  loaded in {time.perf_counter() - t0:.1f}s on {device}")

    per_image: list[dict] = []
    cer_raw_all: list[float] = []
    cer_pp_all: list[float] = []
    wer_raw_all: list[float] = []
    wer_pp_all: list[float] = []

    for idx, (img_path, gold) in enumerate(samples):
        full_path = args.data_root / img_path
        if not full_path.exists():
            continue

        # Tesseract OCR (single line, --psm 7)
        with Image.open(full_path) as im:
            ocr_raw = pytesseract.image_to_string(im, lang="vie", config="--psm 7")
        ocr_raw = unicodedata.normalize("NFC", ocr_raw).strip()

        # Post-correct
        if ocr_raw:
            x = tok(
                ocr_raw,
                return_tensors="pt",
                max_length=256,
                truncation=True,
            ).to(device)
            with torch.no_grad():
                out = model.generate(**x, max_length=256, num_beams=1)
            ocr_pp = unicodedata.normalize(
                "NFC", tok.decode(out[0], skip_special_tokens=True)
            ).strip()
        else:
            ocr_pp = ""

        cer_raw = _cer(ocr_raw, gold)
        cer_pp = _cer(ocr_pp, gold)
        wer_raw = _wer(ocr_raw, gold)
        wer_pp = _wer(ocr_pp, gold)

        cer_raw_all.append(cer_raw)
        cer_pp_all.append(cer_pp)
        wer_raw_all.append(wer_raw)
        wer_pp_all.append(wer_pp)
        per_image.append(
            {
                "image": img_path,
                "gold": gold,
                "ocr_raw": ocr_raw,
                "ocr_post_correct": ocr_pp,
                "cer_raw": round(cer_raw, 4),
                "cer_post_correct": round(cer_pp, 4),
                "wer_raw": round(wer_raw, 4),
                "wer_post_correct": round(wer_pp, 4),
                "cer_delta": round(cer_pp - cer_raw, 4),
            }
        )

        if (idx + 1) % 50 == 0:
            print(
                f"  {idx + 1}/{len(samples)} "
                f"CER raw {statistics.mean(cer_raw_all) * 100:.2f} % "
                f"-> pp {statistics.mean(cer_pp_all) * 100:.2f} %"
            )

    cer_raw_mean = statistics.mean(cer_raw_all)
    cer_pp_mean = statistics.mean(cer_pp_all)
    wer_raw_mean = statistics.mean(wer_raw_all)
    wer_pp_mean = statistics.mean(wer_pp_all)
    n_helped = sum(1 for r in per_image if r["cer_delta"] < -0.001)
    n_neutral = sum(1 for r in per_image if abs(r["cer_delta"]) <= 0.001)
    n_hurt = sum(1 for r in per_image if r["cer_delta"] > 0.001)

    # Bucket by raw CER to see where post-correct helps.
    buckets = {"<10%": [], "10-30%": [], "30-50%": [], "50%+": []}
    for r in per_image:
        c = r["cer_raw"]
        if c < 0.10:
            buckets["<10%"].append(r)
        elif c < 0.30:
            buckets["10-30%"].append(r)
        elif c < 0.50:
            buckets["30-50%"].append(r)
        else:
            buckets["50%+"].append(r)

    print(f"\n=== aggregate (n={len(per_image)}, real handwriting) ===")
    print(f"  CER raw            : {cer_raw_mean * 100:6.2f} %")
    print(
        f"  CER post-correct   : {cer_pp_mean * 100:6.2f} %  ({(cer_pp_mean - cer_raw_mean) * 100:+.2f} pp)"
    )
    print(f"  WER raw            : {wer_raw_mean * 100:6.2f} %")
    print(
        f"  WER post-correct   : {wer_pp_mean * 100:6.2f} %  ({(wer_pp_mean - wer_raw_mean) * 100:+.2f} pp)"
    )
    print(f"  helped / neutral / hurt : {n_helped} / {n_neutral} / {n_hurt}")

    print("\n  Per-bucket (by Tesseract raw CER):")
    print(
        f"  {'bucket':<10s} {'n':>4s} {'CER raw':>10s} {'CER pp':>10s} {'Δ CER':>8s} {'helped':>7s}"
    )
    for name, rows in buckets.items():
        if not rows:
            continue
        c_raw = statistics.mean([r["cer_raw"] for r in rows]) * 100
        c_pp = statistics.mean([r["cer_post_correct"] for r in rows]) * 100
        h = sum(1 for r in rows if r["cer_delta"] < -0.001)
        print(
            f"  {name:<10s} {len(rows):>4d} {c_raw:>9.2f}% {c_pp:>9.2f}% {c_pp - c_raw:>+7.2f} {h:>7d}"
        )

    if args.examples > 0:
        print(f"\n  --- {args.examples} sample (gold / raw / pp) ---")
        # Pick examples spread across CER buckets.
        per_image.sort(key=lambda r: r["cer_raw"])
        step = max(1, len(per_image) // args.examples)
        for r in per_image[::step][: args.examples]:
            print(f"    {r['image']}")
            print(f"      GOLD: {r['gold']}")
            print(f"      RAW : {r['ocr_raw']}  (CER {r['cer_raw'] * 100:.1f} %)")
            print(f"      PP  : {r['ocr_post_correct']}  (CER {r['cer_post_correct'] * 100:.1f} %)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        # Per-image dump is large — only keep aggregate + bucketed in JSON.
        bucket_summary = {}
        for name, rows in buckets.items():
            if not rows:
                bucket_summary[name] = {"n": 0}
                continue
            bucket_summary[name] = {
                "n": len(rows),
                "cer_raw_mean": round(statistics.mean([r["cer_raw"] for r in rows]), 4),
                "cer_post_correct_mean": round(
                    statistics.mean([r["cer_post_correct"] for r in rows]), 4
                ),
                "n_helped": sum(1 for r in rows if r["cer_delta"] < -0.001),
                "n_hurt": sum(1 for r in rows if r["cer_delta"] > 0.001),
            }
        args.json.write_text(
            json.dumps(
                {
                    "ocr_engine": "tesseract-vie",
                    "post_correct_model": args.corrector,
                    "dataset": "brianhuster/VietnameseOCRdataset (line, handwriting)",
                    "license": "Apache-2.0",
                    "n_samples": len(per_image),
                    "seed": args.seed,
                    "cer_raw_mean": round(cer_raw_mean, 4),
                    "cer_post_correct_mean": round(cer_pp_mean, 4),
                    "wer_raw_mean": round(wer_raw_mean, 4),
                    "wer_post_correct_mean": round(wer_pp_mean, 4),
                    "n_helped": n_helped,
                    "n_neutral": n_neutral,
                    "n_hurt": n_hurt,
                    "buckets": bucket_summary,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
        print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
