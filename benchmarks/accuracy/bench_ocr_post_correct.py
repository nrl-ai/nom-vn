"""Bench Tesseract + spell-correction post-processing on VN OCR.

Hypothesis: running our Vietnamese spell-correction model on Tesseract
output should lower CER below the Tesseract-only baseline. If yes, we
ship a "Tesseract + post-correct" pipeline that beats both.

Pipeline:

    image → Tesseract `vie` → text_a   (baseline)
    text_a → vn-spell-correction-base → text_b   (post-corrected)

Metrics (NFC-normalized on both sides):

    CER   = Levenshtein(pred, gold) / len(gold)
    WER   = Levenshtein-on-words(pred.split(), gold.split()) / len(gold.split())

Reports baseline vs post-corrected for both clean + noisy variants of
the synthetic_ocr_vi test bed (20 images each), plus per-image CER
deltas so we can see where post-correct helps and where it hurts.

Usage::

    python benchmarks/accuracy/bench_ocr_post_correct.py \\
        --json benchmarks/results/baseline_ocr_post_correct.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _cer(pred: str, gold: str) -> float:
    """Character error rate via Levenshtein, NFC-normalized."""
    pred = unicodedata.normalize("NFC", pred).strip()
    gold = unicodedata.normalize("NFC", gold).strip()
    if not gold:
        return 0.0 if not pred else 1.0
    # Inline Levenshtein for the small strings we benchmark on.
    n, m = len(pred), len(gold)
    if n == 0:
        return 1.0
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if pred[i - 1] == gold[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[m] / len(gold)


def _wer(pred: str, gold: str) -> float:
    """Word error rate via word-level Levenshtein."""
    p_toks = unicodedata.normalize("NFC", pred).split()
    g_toks = unicodedata.normalize("NFC", gold).split()
    if not g_toks:
        return 0.0 if not p_toks else 1.0
    n, m = len(p_toks), len(g_toks)
    if n == 0:
        return 1.0
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if p_toks[i - 1] == g_toks[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[m] / len(g_toks)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-dir",
        type=Path,
        default=REPO / "benchmarks" / "data" / "synthetic_ocr_vi",
    )
    p.add_argument(
        "--corrector",
        default="nrl-ai/vn-spell-correction-base",
        help="HF repo id of the post-correct model.",
    )
    p.add_argument("--json", type=Path, default=None)
    p.add_argument(
        "--variants",
        default="clean,noisy,hard",
        help="Comma-separated subset of synthetic_ocr_vi variants to bench.",
    )
    p.add_argument("--examples", type=int, default=3)
    args = p.parse_args()

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        print(f"missing dep: {exc}", file=sys.stderr)
        return 2

    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    # The clean+noisy variants share `ground_truth.jsonl`; the hard
    # variant has its own `ground_truth_hard.jsonl` (different sample
    # of sentences, smaller font sizes).
    samples_by_variant: dict[str, list[dict]] = {}
    for variant in args.variants.split(","):
        variant = variant.strip()
        gt_name = "ground_truth_hard.jsonl" if variant == "hard" else "ground_truth.jsonl"
        gt_path = args.data_dir / gt_name
        if not gt_path.exists():
            print(f"skip {variant}: {gt_path} missing", file=sys.stderr)
            continue
        rows: list[dict] = []
        for line in gt_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        samples_by_variant[variant] = rows
        print(f"loaded {len(rows)} samples for variant={variant}")

    print(f"loading corrector {args.corrector}...")
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(args.corrector)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForSeq2SeqLM.from_pretrained(args.corrector).to(device).eval()
    print(f"  loaded in {time.perf_counter() - t0:.1f}s on {device}")

    summary: dict = {}
    for variant, samples in samples_by_variant.items():
        per_image: list[dict] = []
        cer_raw_all: list[float] = []
        cer_pp_all: list[float] = []
        wer_raw_all: list[float] = []
        wer_pp_all: list[float] = []

        for s in samples:
            # hard variant uses an "image" key; clean/noisy use the
            # variant name as the key.
            img_path = args.data_dir / s.get(variant, s.get("image", ""))
            if not img_path.exists():
                continue
            gold = s["text"]

            # Tesseract OCR
            with Image.open(img_path) as im:
                ocr_raw = pytesseract.image_to_string(im, lang="vie", config="--psm 7")
            ocr_raw = unicodedata.normalize("NFC", ocr_raw).strip()

            # Post-correct
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
                    "id": s["id"],
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

        cer_raw_mean = statistics.mean(cer_raw_all)
        cer_pp_mean = statistics.mean(cer_pp_all)
        wer_raw_mean = statistics.mean(wer_raw_all)
        wer_pp_mean = statistics.mean(wer_pp_all)
        n_helped = sum(1 for r in per_image if r["cer_delta"] < -0.001)
        n_neutral = sum(1 for r in per_image if abs(r["cer_delta"]) <= 0.001)
        n_hurt = sum(1 for r in per_image if r["cer_delta"] > 0.001)

        summary[variant] = {
            "n_images": len(per_image),
            "cer_raw_mean": round(cer_raw_mean, 4),
            "cer_post_correct_mean": round(cer_pp_mean, 4),
            "cer_delta_mean": round(cer_pp_mean - cer_raw_mean, 4),
            "wer_raw_mean": round(wer_raw_mean, 4),
            "wer_post_correct_mean": round(wer_pp_mean, 4),
            "n_helped": n_helped,
            "n_neutral": n_neutral,
            "n_hurt": n_hurt,
            "per_image": per_image,
        }

        print(f"\n=== variant: {variant} (n={len(per_image)}) ===")
        print(f"  CER  raw           : {cer_raw_mean * 100:6.2f} %")
        print(
            f"  CER  post-correct  : {cer_pp_mean * 100:6.2f} %  ({(cer_pp_mean - cer_raw_mean) * 100:+.2f} pp)"
        )
        print(f"  WER  raw           : {wer_raw_mean * 100:6.2f} %")
        print(
            f"  WER  post-correct  : {wer_pp_mean * 100:6.2f} %  ({(wer_pp_mean - wer_raw_mean) * 100:+.2f} pp)"
        )
        print(f"  helped / neutral / hurt : {n_helped} / {n_neutral} / {n_hurt}")

        if args.examples > 0:
            print()
            print(f"  --- {args.examples} example outputs ---")
            for r in per_image[: args.examples]:
                print(f"    id={r['id']}")
                print(f"      GOLD: {r['gold']}")
                print(f"      RAW : {r['ocr_raw']}  (CER {r['cer_raw'] * 100:.1f} %)")
                print(
                    f"      PP  : {r['ocr_post_correct']}  (CER {r['cer_post_correct'] * 100:.1f} %)"
                )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "ocr_engine": "tesseract-vie",
                    "post_correct_model": args.corrector,
                    "data_dir": str(args.data_dir.relative_to(REPO)),
                    "variants": list(summary.keys()),
                    "summary": summary,
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
