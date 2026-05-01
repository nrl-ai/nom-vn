"""Diagnose WHY the OCR-correction fine-tune made things worse.

Re-runs Tesseract + the fine-tuned corrector on a fresh sample of the
held-out test split and emits per-image features so we can answer
specific questions:

  1. Does CER worsening correlate with raw CER bucket? (i.e. is post-
     correct safe at low CER but catastrophic at high CER?)
  2. Are post-correct outputs systematically too long / too short
     vs gold? (pure-hallucination usually generates more tokens)
  3. How often does the model invent words that aren't even in the
     raw OCR input? (the "police vs economy" failure)
  4. How often does post-correct regenerate the same sentence
     regardless of input? (mode-collapse / context-ignoring)
  5. Does the fine-tuned model do better than off-the-shelf in any
     specific bucket?

Output: a markdown report with per-bucket numbers + sample failures.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "benchmarks" / "accuracy"))
from bench_ocr_post_correct import _cer, _wer  # noqa: E402
from bench_ocr_post_correct_real import _load_annotations  # noqa: E402


def _word_overlap(a: str, b: str) -> float:
    """Fraction of words in a that also appear in b."""
    a_set = set(a.split())
    b_set = set(b.split())
    if not a_set:
        return 0.0
    return len(a_set & b_set) / len(a_set)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-root",
        type=Path,
        default=Path("/tmp/brianhuster_ocr/data_line"),
    )
    p.add_argument(
        "--corrector-baseline",
        default="nrl-ai/vn-spell-correction-base",
    )
    p.add_argument(
        "--corrector-finetune",
        default="training/ocr_correction/checkpoints/vit5-ocr-correct/final",
    )
    p.add_argument("--n-samples", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path("/tmp/ocr_postmortem.json"))
    args = p.parse_args()

    annotations = _load_annotations(args.data_root / "test_line_annotation.txt")
    import random

    rng = random.Random(args.seed)
    samples = rng.sample(annotations, k=min(args.n_samples, len(annotations)))
    print(f"sampled {len(samples)} from test split (seed={args.seed})")

    import pytesseract
    import torch
    from PIL import Image
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"loading {args.corrector_baseline}...")
    tok_b = AutoTokenizer.from_pretrained(args.corrector_baseline)
    model_b = AutoModelForSeq2SeqLM.from_pretrained(args.corrector_baseline).to(device).eval()

    print(f"loading {args.corrector_finetune}...")
    tok_f = AutoTokenizer.from_pretrained(args.corrector_finetune)
    model_f = AutoModelForSeq2SeqLM.from_pretrained(args.corrector_finetune).to(device).eval()

    def _generate(model, tok, text: str) -> str:
        x = tok(text, return_tensors="pt", max_length=256, truncation=True).to(device)
        with torch.no_grad():
            out = model.generate(**x, max_length=256, num_beams=1)
        return unicodedata.normalize("NFC", tok.decode(out[0], skip_special_tokens=True)).strip()

    rows: list[dict] = []
    finetune_outputs: Counter[str] = Counter()
    t0 = time.perf_counter()
    for idx, (img_rel, gold) in enumerate(samples):
        img = args.data_root / img_rel
        if not img.exists():
            continue
        with Image.open(img) as im:
            raw = pytesseract.image_to_string(im, lang="vie", config="--psm 7")
        raw = unicodedata.normalize("NFC", raw).strip()
        pp_b = _generate(model_b, tok_b, raw) if raw else ""
        pp_f = _generate(model_f, tok_f, raw) if raw else ""

        rows.append(
            {
                "img": img_rel,
                "gold": gold,
                "raw": raw,
                "pp_baseline": pp_b,
                "pp_finetune": pp_f,
                "len_gold_chars": len(gold),
                "len_raw_chars": len(raw),
                "len_pp_b_chars": len(pp_b),
                "len_pp_f_chars": len(pp_f),
                "cer_raw": _cer(raw, gold),
                "cer_pp_b": _cer(pp_b, gold),
                "cer_pp_f": _cer(pp_f, gold),
                "wer_raw": _wer(raw, gold),
                "wer_pp_b": _wer(pp_b, gold),
                "wer_pp_f": _wer(pp_f, gold),
                "wo_raw_in_gold": _word_overlap(raw, gold),
                "wo_pp_b_in_raw": _word_overlap(pp_b, raw),
                "wo_pp_f_in_raw": _word_overlap(pp_f, raw),
                "wo_pp_f_in_gold": _word_overlap(pp_f, gold),
            }
        )
        finetune_outputs[pp_f] += 1
        if (idx + 1) % 50 == 0:
            print(
                f"  {idx + 1}/{len(samples)} ({(idx + 1) / (time.perf_counter() - t0):.1f} img/s)"
            )

    # ---- Analysis ----
    print()
    print(f"=== Diagnosis (n={len(rows)}) ===")
    print()

    # Bucket by raw CER
    buckets = {
        "<10%": [],
        "10-30%": [],
        "30-50%": [],
        "50-70%": [],
        "70%+": [],
    }
    for r in rows:
        c = r["cer_raw"]
        key = (
            "<10%"
            if c < 0.10
            else "10-30%"
            if c < 0.30
            else "30-50%"
            if c < 0.50
            else "50-70%"
            if c < 0.70
            else "70%+"
        )
        buckets[key].append(r)

    print("Per-bucket CER (mean):")
    print(
        f"  {'bucket':<10s} {'n':>4s} {'CER raw':>9s} {'CER base':>10s} {'Δ base':>8s} {'CER ft':>9s} {'Δ ft':>8s}"
    )
    for name, rs in buckets.items():
        if not rs:
            continue
        c_raw = statistics.mean(r["cer_raw"] for r in rs) * 100
        c_b = statistics.mean(r["cer_pp_b"] for r in rs) * 100
        c_f = statistics.mean(r["cer_pp_f"] for r in rs) * 100
        print(
            f"  {name:<10s} {len(rs):>4d} {c_raw:>8.2f}% {c_b:>9.2f}% "
            f"{c_b - c_raw:>+7.2f} {c_f:>8.2f}% {c_f - c_raw:>+7.2f}"
        )

    # Length analysis: are post-correct outputs longer/shorter than gold?
    print()
    print("Length analysis (mean chars):")
    print(f"  gold       {statistics.mean(r['len_gold_chars'] for r in rows):.1f}")
    print(f"  raw        {statistics.mean(r['len_raw_chars'] for r in rows):.1f}")
    print(f"  pp_base    {statistics.mean(r['len_pp_b_chars'] for r in rows):.1f}")
    print(f"  pp_finetune {statistics.mean(r['len_pp_f_chars'] for r in rows):.1f}")

    # Hallucination indicator: words in pp that AREN'T in raw
    print()
    print("Hallucination indicator (fraction of pp words NOT in raw OCR):")
    halluc_b = 1 - statistics.mean(r["wo_pp_b_in_raw"] for r in rows)
    halluc_f = 1 - statistics.mean(r["wo_pp_f_in_raw"] for r in rows)
    print(f"  pp_base    {halluc_b * 100:.2f} %")
    print(f"  pp_finetune {halluc_f * 100:.2f} %  (higher = more invention)")

    # Mode collapse: how diverse are the fine-tuned outputs?
    n_unique = len(finetune_outputs)
    most_common = finetune_outputs.most_common(5)
    print()
    print("Mode collapse check (fine-tune output diversity):")
    print(f"  unique outputs: {n_unique} / {len(rows)}")
    print("  top 5 most-repeated outputs:")
    for s, c in most_common:
        print(f"    [{c:>2d}x] {s[:100]}")

    # Catastrophic failures
    print()
    print("Worst 5 finetune regressions (largest CER worsening):")
    rows_by_ft_delta = sorted(rows, key=lambda r: r["cer_pp_f"] - r["cer_raw"], reverse=True)
    for r in rows_by_ft_delta[:5]:
        print(
            f"  CER raw {r['cer_raw'] * 100:.0f}% -> ft {r['cer_pp_f'] * 100:.0f}% (+{(r['cer_pp_f'] - r['cer_raw']) * 100:.0f} pp)"
        )
        print(f"    GOLD: {r['gold'][:120]}")
        print(f"    RAW : {r['raw'][:120]}")
        print(f"    FT  : {r['pp_finetune'][:120]}")

    # Best 5 helped
    print()
    print("Best 5 finetune wins (largest CER improvement):")
    for r in rows_by_ft_delta[-5:][::-1]:
        if r["cer_pp_f"] >= r["cer_raw"]:
            continue
        print(
            f"  CER raw {r['cer_raw'] * 100:.0f}% -> ft {r['cer_pp_f'] * 100:.0f}% ({(r['cer_pp_f'] - r['cer_raw']) * 100:.0f} pp)"
        )
        print(f"    GOLD: {r['gold'][:120]}")
        print(f"    RAW : {r['raw'][:120]}")
        print(f"    FT  : {r['pp_finetune'][:120]}")

    # Save full data for offline poking
    args.out.write_text(
        json.dumps(
            {
                "n_samples": len(rows),
                "buckets": {
                    k: {
                        "n": len(v),
                        "cer_raw_mean": round(
                            statistics.mean(r["cer_raw"] for r in v) if v else 0, 4
                        ),
                        "cer_pp_b_mean": round(
                            statistics.mean(r["cer_pp_b"] for r in v) if v else 0, 4
                        ),
                        "cer_pp_f_mean": round(
                            statistics.mean(r["cer_pp_f"] for r in v) if v else 0, 4
                        ),
                    }
                    for k, v in buckets.items()
                },
                "hallucination_finetune_pct": round(halluc_f * 100, 2),
                "hallucination_baseline_pct": round(halluc_b * 100, 2),
                "n_unique_finetune_outputs": n_unique,
                "rows": rows,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\n  full data: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
