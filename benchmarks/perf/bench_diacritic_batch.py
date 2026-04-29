"""Measure ``HFDiacriticModel.predict`` vs ``predict_batch`` throughput.

CUDA kernel launches dominate per-call cost on short Vietnamese
sentences, so calling ``predict`` in a loop leaves a lot of throughput
on the table. ``predict_batch`` pads a batch to the longest sequence
and issues a single ``generate`` call.

Methodology (per CLAUDE.md principle 12):
    - 3 warmup calls before timing.
    - Best-of-3 wall-clock for each path; report median.
    - Inputs from the 300-sentence Tatoeba conversational corpus
      (representative of typical chat / form input).
    - Same model, same device, same num_beams.

Usage::

    python benchmarks/perf/bench_diacritic_batch.py
    python benchmarks/perf/bench_diacritic_batch.py --batch-size 32 --n 100

Defaults are sized to fit comfortably on a 16 GB-class consumer GPU.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


def _load_corpus(path: Path, n: int) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
            if len(out) >= n:
                break
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--corpus",
        type=Path,
        default=REPO / "benchmarks" / "data" / "tatoeba_vi" / "diacritic_eval_300.txt",
    )
    p.add_argument("--n", type=int, default=120, help="Sentences to process per timed run.")
    p.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Sentences per generate() call in the batched path.",
    )
    p.add_argument(
        "--repeats", type=int, default=3, help="Repeat each path N times; report median."
    )
    p.add_argument(
        "--model-id",
        default="Toshiiiii1/Vietnamese_diacritics_restoration_5th",
    )
    p.add_argument(
        "--json",
        type=Path,
        default=REPO / "benchmarks" / "results" / "baseline_diacritic_batch_speedup.json",
    )
    args = p.parse_args()

    sents = _load_corpus(args.corpus, args.n)
    print(f"corpus: {args.corpus.name} -> {len(sents)} sentences")

    from nom.text.diacritic_models import HFDiacriticModel

    print(f"loading {args.model_id}...")
    model = HFDiacriticModel(model_id=args.model_id)

    # Warmup: trigger model load + 3 single-sentence generations on a
    # short input. The first generation includes kernel compilation and
    # would inflate the single-call timing; subsequent calls are stable.
    print("warmup (3 calls)...")
    for _ in range(3):
        model.predict(sents[0])
    # Also warm the batched path so the first batched call doesn't pay
    # padding-shape compilation costs.
    model.predict_batch(sents[: min(args.batch_size, len(sents))], batch_size=args.batch_size)

    # Single-call path: predict() in a loop.
    print(f"\n--- predict() loop, {args.repeats} runs of {len(sents)} sentences ---")
    single_times: list[float] = []
    for r in range(args.repeats):
        t0 = time.perf_counter()
        single_out = [model.predict(s) for s in sents]
        elapsed = time.perf_counter() - t0
        single_times.append(elapsed)
        print(f"  run {r + 1}: {elapsed:.2f} s ({len(sents) / elapsed:.1f} sent/s)")

    # Batched path.
    print(f"\n--- predict_batch(batch_size={args.batch_size}), {args.repeats} runs ---")
    batch_times: list[float] = []
    for r in range(args.repeats):
        t0 = time.perf_counter()
        batch_out = model.predict_batch(sents, batch_size=args.batch_size)
        elapsed = time.perf_counter() - t0
        batch_times.append(elapsed)
        print(f"  run {r + 1}: {elapsed:.2f} s ({len(sents) / elapsed:.1f} sent/s)")

    # Quality check: outputs must match (allow trailing whitespace differences).
    mismatches = sum(
        1 for s, b in zip(single_out, batch_out, strict=False) if s.strip() != b.strip()
    )
    print(f"\nquality match: {len(sents) - mismatches}/{len(sents)} sentences")
    if mismatches > 0:
        print("  WARN: batched path diverges on some sentences — investigate before shipping.")
        for s, b, src in zip(single_out, batch_out, sents, strict=False):
            if s.strip() != b.strip():
                print(f"    SRC:    {src}")
                print(f"    SINGLE: {s}")
                print(f"    BATCH:  {b}")
                break

    single_med = statistics.median(single_times)
    batch_med = statistics.median(batch_times)
    speedup = single_med / batch_med if batch_med > 0 else 0.0
    print()
    print("=" * 60)
    print(f"  Single (median):     {single_med:.2f} s ({len(sents) / single_med:.1f} sent/s)")
    print(f"  Batched (median):    {batch_med:.2f} s ({len(sents) / batch_med:.1f} sent/s)")
    print(f"  Speedup:             {speedup:.2f}x")
    print("=" * 60)

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(
            {
                "model_id": args.model_id,
                "corpus": str(args.corpus.relative_to(REPO)),
                "n_sentences": len(sents),
                "batch_size": args.batch_size,
                "repeats": args.repeats,
                "single_seconds": [round(t, 4) for t in single_times],
                "batched_seconds": [round(t, 4) for t in batch_times],
                "single_median_seconds": round(single_med, 4),
                "batched_median_seconds": round(batch_med, 4),
                "single_throughput_sent_s": round(len(sents) / single_med, 2),
                "batched_throughput_sent_s": round(len(sents) / batch_med, 2),
                "speedup": round(speedup, 2),
                "quality_match_rate": round((len(sents) - mismatches) / len(sents), 4),
                "warmup_calls": 3,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"results: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
