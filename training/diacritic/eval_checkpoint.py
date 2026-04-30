"""Standalone 4-register eval for any HF seq2seq diacritic-restoration model.

Reuses ``load_eval_corpora`` and ``_word_accuracy`` from ``train.py`` so
the metric definition stays in one place. Loads the model + tokenizer
from a directory (output of ``trainer.save_model``) or an HF Hub repo
ID, runs the 4-register eval, and writes a summary JSON.

Why a separate script: re-evaluating a trained checkpoint shouldn't
require the training data or the heavy Trainer imports; this script
only needs ``transformers`` + ``torch``. Useful for:

- Re-eval after rsyncing a checkpoint back from the GPU training box.
- Comparing the trained checkpoint's numbers against an updated
  eval corpus (e.g. when we add a 5th register).
- Sanity-check before publishing — re-run the eval on the local
  machine to confirm the GPU training box numbers reproduce.

Usage::

    # eval a local checkpoint
    python training/diacritic/eval_checkpoint.py \\
        --checkpoint training/diacritic/checkpoints/vit5-base-500k-cosine/final \\
        --output-json training/diacritic/results/vit5-base-500k_summary.json

    # eval an HF Hub model (off-the-shelf comparison)
    python training/diacritic/eval_checkpoint.py \\
        --checkpoint Toshiiiii1/Vietnamese_diacritics_restoration_5th \\
        --output-json benchmarks/results/baseline_diacritic_toshiiiii_full4register.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from training.diacritic.train import (  # noqa: E402
    _word_accuracy,
    load_eval_corpora,
    normalize_punct,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--checkpoint",
        required=True,
        help="Local directory or HF Hub repo id of the model to eval.",
    )
    p.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Where to write the eval summary.",
    )
    p.add_argument("--max-input-length", type=int, default=256)
    p.add_argument("--max-target-length", type=int, default=256)
    p.add_argument("--num-beams", type=int, default=1)
    p.add_argument(
        "--examples",
        type=int,
        default=3,
        help="Print this many sample (gold, pred) pairs per corpus.",
    )
    p.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Discard the first N generations as warmup before timing.",
    )
    args = p.parse_args()

    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    print(f"loading {args.checkpoint}...")
    t0 = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.checkpoint).to(device).eval()
    print(f"  loaded in {time.perf_counter() - t0:.1f}s")

    corpora = load_eval_corpora(REPO)
    if not corpora:
        print("ERROR: no eval corpora found under benchmarks/data/", file=sys.stderr)
        return 2

    # Warmup — first generations on a fresh CUDA context include kernel
    # compilation; tossing 3 generations gives stable per-sentence latencies.
    if corpora and args.warmup > 0:
        any_corpus = next(iter(corpora.values()))
        warm = any_corpus[0][0]
        for _ in range(args.warmup):
            x = tokenizer(
                warm,
                return_tensors="pt",
                max_length=args.max_input_length,
                truncation=True,
            ).to(device)
            with torch.no_grad():
                model.generate(**x, max_length=args.max_target_length, num_beams=args.num_beams)

    eval_summary: dict[str, dict[str, float]] = {}
    for name, pairs in corpora.items():
        print(f"\n--- {name} ({len(pairs)} sentences) ---")
        preds: list[str] = []
        targets: list[str] = []
        latencies: list[float] = []
        for stripped, target in pairs:
            t_one = time.perf_counter()
            x = tokenizer(
                stripped,
                return_tensors="pt",
                max_length=args.max_input_length,
                truncation=True,
            ).to(device)
            with torch.no_grad():
                out = model.generate(
                    **x, max_length=args.max_target_length, num_beams=args.num_beams
                )
            pred = tokenizer.decode(out[0], skip_special_tokens=True)
            latencies.append(time.perf_counter() - t_one)
            preds.append(pred)
            targets.append(target)
        wa, se = _word_accuracy(preds, targets)
        latencies.sort()
        mean_ms = sum(latencies) / len(latencies) * 1000
        p50_ms = latencies[len(latencies) // 2] * 1000
        p95_ms = latencies[max(0, int(len(latencies) * 0.95) - 1)] * 1000
        eval_summary[name] = {
            "n_sentences": len(pairs),
            "word_accuracy": round(wa, 4),
            "sentence_exact": round(se, 4),
            "mean_ms_per_sentence": round(mean_ms, 2),
            "p50_ms": round(p50_ms, 2),
            "p95_ms": round(p95_ms, 2),
        }
        print(f"  Word accuracy:   {wa:.4f}")
        print(f"  Sentence exact:  {se:.4f}")
        print(f"  Latency:         mean {mean_ms:.1f} ms · p50 {p50_ms:.1f} · p95 {p95_ms:.1f}")
        if args.examples > 0:
            print(f"  First {args.examples} examples:")
            for p, t in zip(preds[: args.examples], targets[: args.examples], strict=False):
                gt = normalize_punct(t)
                pr = normalize_punct(p)
                tag = "MATCH" if gt == pr else "DIFF "
                print(f"    [{tag}] GT:  {gt}")
                print(f"            OUT: {pr}")

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(
            {
                "checkpoint": args.checkpoint,
                "device": device,
                "warmup_calls": args.warmup,
                "num_beams": args.num_beams,
                "max_input_length": args.max_input_length,
                "max_target_length": args.max_target_length,
                "eval": eval_summary,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"\nWrote: {args.output_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
