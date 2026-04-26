"""Bench an HF seq2seq diacritic-restoration model on the 55-sent corpus.

Usage:
    python benchmarks/accuracy/bench_diacritic_hf.py <model_id>
    python benchmarks/accuracy/bench_diacritic_hf.py \\
        Toshiiiii1/Vietnamese_diacritics_restoration_5th \\
        --json benchmarks/results/baseline_diacritic_toshiiiii_t5.json

This is the off-the-shelf bench harness that complements
``bench_diacritics.py`` (which targets rule + LLM backends). Any HF
seq2seq diacritic model exposed via ``AutoModelForSeq2SeqLM`` works.

Note: ``transformers>=5.6`` has a slow-T5-tokenizer regression that
breaks Toshiiiii1's load. Use ``transformers<5`` for now.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

sys.path.insert(0, "src")
from nom.text import has_diacritics, strip_diacritics


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("model_id")
    p.add_argument(
        "--prefix",
        default="",
        help="Optional input prefix (some T5 models need 'restore: ' or similar).",
    )
    p.add_argument(
        "--task",
        choices=("seq2seq", "token-classification"),
        default="seq2seq",
    )
    p.add_argument(
        "--corpus",
        default="benchmarks/data/diacritic_eval_v0.txt",
    )
    p.add_argument("--json", default=None)
    p.add_argument("--examples", type=int, default=2)
    p.add_argument("--num-beams", type=int, default=1)
    args = p.parse_args()

    sentences: list[str] = []
    for raw in Path(args.corpus).read_text(encoding="utf-8").splitlines():
        if raw.strip() and not raw.startswith("#"):
            sentences.append(raw)
    print(f"corpus: {len(sentences)} sentences")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    print(f"loading {args.model_id}...")
    t0 = time.perf_counter()

    if args.task == "seq2seq":
        tok = AutoTokenizer.from_pretrained(args.model_id, use_fast=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(args.model_id).to(device).eval()
    else:
        from transformers import AutoModelForTokenClassification

        tok = AutoTokenizer.from_pretrained(args.model_id, use_fast=True)
        model = AutoModelForTokenClassification.from_pretrained(args.model_id).to(device).eval()
    print(f"loaded in {time.perf_counter() - t0:.1f}s")

    # warmup x3
    warm = strip_diacritics(sentences[0])
    for _ in range(3):
        x = tok(args.prefix + warm, return_tensors="pt", max_length=512, truncation=True).to(device)
        with torch.no_grad():
            if args.task == "seq2seq":
                model.generate(**x, max_length=512, num_beams=args.num_beams)
            else:
                model(**x)

    n_words = n_correct = n_diac = n_diac_rec = 0
    latencies: list[float] = []
    sample_outs: list[tuple[str, str, str]] = []  # (gt, stripped, pred)
    t_total0 = time.perf_counter()
    for orig in sentences:
        stripped = strip_diacritics(orig)
        t0 = time.perf_counter()
        if args.task == "seq2seq":
            x = tok(
                args.prefix + stripped, return_tensors="pt", max_length=512, truncation=True
            ).to(device)
            with torch.no_grad():
                out = model.generate(**x, max_length=512, num_beams=args.num_beams)
            pred = tok.decode(out[0], skip_special_tokens=True)
        else:
            # token classification: each input char -> output char label
            # implementation depends on model's label mapping. Skip generic.
            raise NotImplementedError("token-classification path requires model-specific decoding.")
        latencies.append(time.perf_counter() - t0)
        sample_outs.append((orig, stripped, pred))

        for o, prd in zip(orig.split(), pred.split(), strict=False):
            n_words += 1
            if o == prd:
                n_correct += 1
            if has_diacritics(o):
                n_diac += 1
                if o == prd:
                    n_diac_rec += 1
    elapsed = time.perf_counter() - t_total0

    word_acc = n_correct / n_words if n_words else 0
    diac_recall = n_diac_rec / n_diac if n_diac else 0
    latencies_s = sorted(latencies)
    p50 = latencies_s[len(latencies_s) // 2]
    p95 = latencies_s[max(0, int(len(latencies_s) * 0.95) - 1)]
    mean = sum(latencies) / len(latencies)

    print()
    print(f"{'metric':>30}  {'value':>10}")
    print("-" * 45)
    print(f"{'Word accuracy':>30}  {word_acc:>10.2%}")
    print(f"{'Diacritic recall':>30}  {diac_recall:>10.2%}")
    print(f"{'Mean latency (s/sent)':>30}  {mean:>10.3f}")
    print(f"{'p50 latency (s/sent)':>30}  {p50:>10.3f}")
    print(f"{'p95 latency (s/sent)':>30}  {p95:>10.3f}")
    print(f"{'Total elapsed':>30}  {elapsed:>10.2f}s")
    print()
    print(f"Examples (first {args.examples}):")
    for orig, stripped, pred in sample_outs[: args.examples]:
        print(f"  GT:  {orig}")
        print(f"  IN:  {stripped}")
        print(f"  OUT: {pred}")
        print()

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(
                {
                    "model_id": args.model_id,
                    "device": device,
                    "n_sentences": len(sentences),
                    "n_words": n_words,
                    "word_accuracy": round(word_acc, 4),
                    "diacritic_recall": round(diac_recall, 4),
                    "elapsed_seconds": round(elapsed, 4),
                    "latency_per_sentence_mean": round(mean, 4),
                    "latency_per_sentence_p50": round(p50, 4),
                    "latency_per_sentence_p95": round(p95, 4),
                    "warmup_calls": 3,
                    "prefix": args.prefix,
                    "num_beams": args.num_beams,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print(f"results: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
