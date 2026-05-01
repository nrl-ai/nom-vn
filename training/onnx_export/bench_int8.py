"""Bench an ONNX int8 seq2seq model on the OOD eval set.

Uses the same metric definitions as
``benchmarks/accuracy/bench_spell_correction_real.py`` (NFC + punct
normalization, bootstrap CI, per-error-type breakdown), but loads via
``ORTModelForSeq2SeqLM`` for ONNX support.

Usage::

    python training/onnx_export/bench_int8.py \\
        --model training/onnx_export/vn-spell-correction-small-int8 \\
        --json benchmarks/results/baseline_real_spell_correction_small_onnx_int8.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "benchmarks" / "accuracy"))
from bench_spell_correction_real import (  # noqa: E402
    EVAL_SLICES,
    _bootstrap_ci_word_acc,
    _categorize_errors,
    _load_jsonl,
)
from training.diacritic.train import _word_accuracy  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, help="ONNX dir (or HF repo with ONNX files).")
    p.add_argument("--json", type=Path, default=None)
    p.add_argument(
        "--eval-dir",
        type=Path,
        default=REPO / "benchmarks" / "data" / "spell_correction_eval_real",
    )
    p.add_argument("--max-input-length", type=int, default=256)
    p.add_argument("--max-target-length", type=int, default=256)
    p.add_argument("--num-beams", type=int, default=1)
    p.add_argument("--warmup", type=int, default=3)
    args = p.parse_args()

    from optimum.onnxruntime import ORTModelForSeq2SeqLM
    from transformers import AutoTokenizer

    print(f"Loading {args.model} (ORT)...")
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(args.model)
    model = ORTModelForSeq2SeqLM.from_pretrained(args.model)
    print(f"  loaded in {time.perf_counter() - t0:.1f}s")

    # Warmup
    if args.warmup > 0:
        any_jsonl = sorted(args.eval_dir.glob("*.jsonl"))[0]
        warm = _load_jsonl(any_jsonl)[0][0]
        for _ in range(args.warmup):
            x = tok(warm, return_tensors="pt", max_length=args.max_input_length, truncation=True)
            model.generate(**x, max_length=args.max_target_length, num_beams=args.num_beams)

    eval_summary: dict[str, dict] = {}
    all_preds: list[str] = []
    all_targets: list[str] = []

    for name in EVAL_SLICES:
        path = args.eval_dir / f"{name}.jsonl"
        if not path.exists():
            continue
        pairs = _load_jsonl(path)
        print(f"\n--- {name} ({len(pairs)} sentences) ---")
        preds: list[str] = []
        targets: list[str] = []
        latencies: list[float] = []
        for noisy, target in pairs:
            t_one = time.perf_counter()
            x = tok(
                noisy,
                return_tensors="pt",
                max_length=args.max_input_length,
                truncation=True,
            )
            out = model.generate(**x, max_length=args.max_target_length, num_beams=args.num_beams)
            pred = tok.decode(out[0], skip_special_tokens=True)
            latencies.append(time.perf_counter() - t_one)
            preds.append(unicodedata.normalize("NFC", pred))
            targets.append(target)
        latencies.sort()
        wa, se = _word_accuracy(preds, targets)
        ci_lo, ci_hi = _bootstrap_ci_word_acc(preds, targets)
        err_counts = _categorize_errors(preds, targets)
        mean_ms = sum(latencies) / len(latencies) * 1000
        p50_ms = latencies[len(latencies) // 2] * 1000
        p95_ms = latencies[max(0, int(len(latencies) * 0.95) - 1)] * 1000
        eval_summary[name] = {
            "n_sentences": len(pairs),
            "word_accuracy": round(wa, 4),
            "word_accuracy_ci95": [round(ci_lo, 4), round(ci_hi, 4)],
            "sentence_exact": round(se, 4),
            "errors": err_counts,
            "mean_ms_per_sentence": round(mean_ms, 2),
            "p50_ms": round(p50_ms, 2),
            "p95_ms": round(p95_ms, 2),
        }
        print(f"  Word accuracy:   {wa:.4f} [95% CI {ci_lo:.4f}-{ci_hi:.4f}]")
        print(f"  Sentence exact:  {se:.4f}")
        print(f"  Latency:         mean {mean_ms:.1f} ms · p50 {p50_ms:.1f} · p95 {p95_ms:.1f}")
        all_preds.extend(preds)
        all_targets.extend(targets)

    if all_preds:
        wa_all, se_all = _word_accuracy(all_preds, all_targets)
        ci_lo, ci_hi = _bootstrap_ci_word_acc(all_preds, all_targets)
        err_counts = _categorize_errors(all_preds, all_targets)
        eval_summary["__all_real__"] = {
            "n_sentences": len(all_preds),
            "word_accuracy": round(wa_all, 4),
            "word_accuracy_ci95": [round(ci_lo, 4), round(ci_hi, 4)],
            "sentence_exact": round(se_all, 4),
            "errors": err_counts,
        }
        print()
        print(
            f"=== aggregate (n={len(all_preds)}): "
            f"word_acc={wa_all:.4f} [95% CI {ci_lo:.4f}-{ci_hi:.4f}] "
            f"sentence_exact={se_all:.4f} ==="
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "model_id": str(args.model),
                    "format": "onnx-int8",
                    "warmup_calls": args.warmup,
                    "num_beams": args.num_beams,
                    "eval": eval_summary,
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
