"""Bench OCR + post-correct with inference-time guardrails.

The diagnosis (analyze_failure.py) found three concrete failure modes:

  1. Hallucination — model invents words not in the raw OCR (91 % of
     fine-tune output words don't appear in the input).
  2. Length collapse — outputs are 41 % shorter than gold on average.
  3. N-gram looping — degenerate greedy decoding produces repetitive
     output ('việc làm việc làm việc làm...').

This script applies four guardrails at inference time and re-measures:

  - **Beam search** (num_beams=4, length_penalty=1.0) reduces greedy
    hallucination.
  - **No-repeat n-gram** (no_repeat_ngram_size=3) blocks loops.
  - **Length-conditioned max_length** (1.5x input tokens) prevents
    runaway generation when input is short.
  - **Confidence gate** — skip post-correct entirely if raw OCR has
    fewer than `min-vn-chars` Vietnamese diacritic characters
    (a proxy for "this is not recognizable Vietnamese, don't try to
    correct it").

Tests the off-the-shelf model + the fine-tuned model under both the
old greedy settings and the new guardrails.

Usage::

    python training/ocr_correction/bench_with_guards.py \\
        --json benchmarks/results/baseline_ocr_post_correct_real_guarded.json
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
sys.path.insert(0, str(REPO / "benchmarks" / "accuracy"))
from bench_ocr_post_correct import _cer, _wer  # noqa: E402
from bench_ocr_post_correct_real import _load_annotations  # noqa: E402

# Vietnamese diacritic codepoints (precomposed) — used for the
# confidence gate. Unicode ranges:
#   U+1EA0-U+1EF9   precomposed VN-specific letters with tone marks
#   U+00C0-U+1EF9   broader Latin Extended ranges that include VN
VN_DIACRITIC_RANGES = [
    (0x00C0, 0x024F),
    (0x1E00, 0x1EFF),
]


def _count_vn_diacritic_chars(text: str) -> int:
    n = 0
    for ch in text:
        cp = ord(ch)
        for lo, hi in VN_DIACRITIC_RANGES:
            if lo <= cp <= hi:
                n += 1
                break
    return n


def _confidence_gate_passes(raw: str, min_vn_chars: int = 2, min_alpha_ratio: float = 0.40) -> bool:
    """Return True if the raw OCR looks Vietnamese enough to bother correcting."""
    if not raw:
        return False
    if _count_vn_diacritic_chars(raw) < min_vn_chars:
        return False
    n_alpha = sum(1 for c in raw if c.isalpha())
    return not n_alpha / max(1, len(raw)) < min_alpha_ratio


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-root",
        type=Path,
        default=Path("/tmp/brianhuster_ocr/data_line"),
    )
    p.add_argument("--n-samples", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--correctors",
        default="nrl-ai/vn-spell-correction-base,training/ocr_correction/checkpoints/vit5-ocr-correct/final",
    )
    p.add_argument("--num-beams", type=int, default=4)
    p.add_argument("--length-penalty", type=float, default=1.0)
    p.add_argument("--no-repeat-ngram-size", type=int, default=3)
    p.add_argument("--max-input-length", type=int, default=256)
    p.add_argument("--min-vn-chars", type=int, default=2)
    p.add_argument("--min-alpha-ratio", type=float, default=0.40)
    p.add_argument("--json", type=Path, default=None)
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
    correctors = [c.strip() for c in args.correctors.split(",") if c.strip()]
    loaded: dict = {}
    for c in correctors:
        print(f"loading {c}...")
        t0 = time.perf_counter()
        loaded[c] = (
            AutoTokenizer.from_pretrained(c),
            AutoModelForSeq2SeqLM.from_pretrained(c).to(device).eval(),
        )
        print(f"  loaded in {time.perf_counter() - t0:.1f}s")

    def _gen_greedy(model, tok, raw: str) -> str:
        x = tok(raw, return_tensors="pt", max_length=args.max_input_length, truncation=True).to(
            device
        )
        with torch.no_grad():
            out = model.generate(**x, max_length=args.max_input_length, num_beams=1)
        return unicodedata.normalize("NFC", tok.decode(out[0], skip_special_tokens=True)).strip()

    def _gen_guarded(model, tok, raw: str) -> str:
        # 1. Confidence gate: skip if input doesn't look like VN.
        if not _confidence_gate_passes(raw, args.min_vn_chars, args.min_alpha_ratio):
            return raw  # pass-through; corrector "abstains"
        # 2. Length-conditioned generation: max_new_tokens scales with input.
        x = tok(raw, return_tensors="pt", max_length=args.max_input_length, truncation=True).to(
            device
        )
        input_len = x["input_ids"].shape[1]
        max_len = min(args.max_input_length, max(16, int(input_len * 1.5)))
        # 3. Beam search + 4. No-repeat n-gram.
        with torch.no_grad():
            out = model.generate(
                **x,
                max_length=max_len,
                num_beams=args.num_beams,
                length_penalty=args.length_penalty,
                no_repeat_ngram_size=args.no_repeat_ngram_size,
                early_stopping=True,
            )
        return unicodedata.normalize("NFC", tok.decode(out[0], skip_special_tokens=True)).strip()

    # Per-config CER + WER.
    configs: dict = {
        "raw_only": {"raw_only": True},
    }
    for c in correctors:
        configs[f"{c} (greedy)"] = {"corrector": c, "mode": "greedy"}
        configs[f"{c} (guarded)"] = {"corrector": c, "mode": "guarded"}

    results: dict = {name: {"cers": [], "wers": [], "skipped": 0} for name in configs}
    rows: list[dict] = []

    t0 = time.perf_counter()
    for idx, (img_rel, gold) in enumerate(samples):
        img = args.data_root / img_rel
        if not img.exists():
            continue
        with Image.open(img) as im:
            raw = pytesseract.image_to_string(im, lang="vie", config="--psm 7")
        raw = unicodedata.normalize("NFC", raw).strip()

        row: dict = {"img": img_rel, "gold": gold, "raw": raw}
        for name, cfg in configs.items():
            if cfg.get("raw_only"):
                pred = raw
            else:
                tok, model = loaded[cfg["corrector"]]
                if cfg["mode"] == "greedy":
                    pred = _gen_greedy(model, tok, raw) if raw else ""
                else:
                    pred = _gen_guarded(model, tok, raw) if raw else ""
                    if pred == raw:
                        results[name]["skipped"] += 1
            cer = _cer(pred, gold)
            wer = _wer(pred, gold)
            results[name]["cers"].append(cer)
            results[name]["wers"].append(wer)
            row[name] = pred
            row[f"{name}_cer"] = round(cer, 4)
        rows.append(row)
        if (idx + 1) % 50 == 0:
            print(
                f"  {idx + 1}/{len(samples)} ({(idx + 1) / (time.perf_counter() - t0):.1f} img/s)"
            )

    # Report.
    print()
    print("=== Aggregate (n=" + str(len(rows)) + ") ===")
    print(f"  {'config':<70s} {'CER':>8s} {'WER':>8s} {'gate-skipped':>14s}")
    for name, agg in results.items():
        c = statistics.mean(agg["cers"]) * 100
        w = statistics.mean(agg["wers"]) * 100
        print(f"  {name[:68]:<70s} {c:>7.2f}% {w:>7.2f}% {agg['skipped']:>14d}")

    # vs raw_only deltas.
    raw_cer = statistics.mean(results["raw_only"]["cers"]) * 100
    raw_wer = statistics.mean(results["raw_only"]["wers"]) * 100
    print()
    print("  Δ vs raw-only (positive = worse):")
    for name, agg in results.items():
        if name == "raw_only":
            continue
        d_c = statistics.mean(agg["cers"]) * 100 - raw_cer
        d_w = statistics.mean(agg["wers"]) * 100 - raw_wer
        print(f"  {name[:68]:<70s} {d_c:>+7.2f}pp {d_w:>+7.2f}pp")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "n_samples": len(rows),
                    "seed": args.seed,
                    "guards": {
                        "num_beams": args.num_beams,
                        "length_penalty": args.length_penalty,
                        "no_repeat_ngram_size": args.no_repeat_ngram_size,
                        "min_vn_chars": args.min_vn_chars,
                        "min_alpha_ratio": args.min_alpha_ratio,
                    },
                    "results": {
                        name: {
                            "cer_mean": round(statistics.mean(agg["cers"]), 4),
                            "wer_mean": round(statistics.mean(agg["wers"]), 4),
                            "n_gate_skipped": agg["skipped"],
                        }
                        for name, agg in results.items()
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print(f"\n  Results: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
