"""Accuracy benchmark for ``nom.text.fix_diacritics``.

Loads ``benchmarks/data/diacritic_eval_v0.txt`` (55 hand-curated VN sentences
across business, official, conversational, and news registers), strips
diacritics from each sentence, calls ``fix_diacritics``, and measures
word-level recovery accuracy.

This benchmark establishes the v0.0.1 baseline. The current implementation
uses a small curated vocabulary, so accuracy on out-of-vocabulary words is
0% by design — recovery comes from common business words and particles.

Run:
    python benchmarks/accuracy/bench_diacritics.py
    python benchmarks/accuracy/bench_diacritics.py --json results.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from nom.text import fix_diacritics, has_diacritics, strip_diacritics

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "benchmarks" / "data" / "diacritic_eval_v0.txt"


@dataclass
class SentenceResult:
    register: str
    original: str
    stripped: str
    restored: str
    word_total: int
    word_correct: int
    word_with_diacritic: int
    word_diacritic_recovered: int
    latency_seconds: float = 0.0

    @property
    def word_accuracy(self) -> float:
        return self.word_correct / self.word_total if self.word_total else 0.0

    @property
    def diacritic_recall(self) -> float:
        # Of words that had diacritics in the ground truth, how many did we restore?
        if self.word_with_diacritic == 0:
            return 1.0
        return self.word_diacritic_recovered / self.word_with_diacritic


@dataclass
class BenchSummary:
    n_sentences: int
    n_words: int
    n_words_with_diacritic: int
    overall_word_accuracy: float
    overall_diacritic_recall: float
    by_register: dict[str, dict[str, float | int]]
    elapsed_seconds: float
    latency_per_sentence_mean: float = 0.0
    latency_per_sentence_p50: float = 0.0
    latency_per_sentence_p95: float = 0.0
    warmup_calls: int = 0


def _load_corpus(path: Path) -> list[tuple[str, str]]:
    """Read the eval corpus — list of (register, sentence) tuples."""
    pairs: list[tuple[str, str]] = []
    register = "unknown"
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("# ===") and "register:" in line:
                # Parse "# === register: contracts / business ==="
                register = line.split("register:", 1)[1].rsplit("===", 1)[0].strip()
                continue
            if line.startswith("#"):
                continue
            pairs.append((register, line))
    return pairs


def _word_compare(original: str, restored: str) -> tuple[int, int, int, int]:
    """Returns (total, correct, with_diacritic, diacritic_recovered)."""
    orig_tokens = original.split()
    rest_tokens = restored.split()
    total = len(orig_tokens)
    correct = 0
    with_diac = 0
    diac_recovered = 0
    # Align by index — tokenization matches because we only stripped/restored
    # diacritics, never added/removed words.
    for o, r in zip(orig_tokens, rest_tokens, strict=False):
        if o == r:
            correct += 1
        if has_diacritics(o):
            with_diac += 1
            if o == r:
                diac_recovered += 1
    return total, correct, with_diac, diac_recovered


def _aggregate_by_register(results: Iterable[SentenceResult]) -> dict[str, dict[str, float | int]]:
    buckets: dict[str, list[SentenceResult]] = {}
    for r in results:
        buckets.setdefault(r.register, []).append(r)
    out: dict[str, dict[str, float | int]] = {}
    for reg, rs in buckets.items():
        total = sum(r.word_total for r in rs)
        correct = sum(r.word_correct for r in rs)
        with_d = sum(r.word_with_diacritic for r in rs)
        rec_d = sum(r.word_diacritic_recovered for r in rs)
        out[reg] = {
            "n_sentences": len(rs),
            "n_words": total,
            "word_accuracy": round(correct / total, 4) if total else 0.0,
            "diacritic_recall": round(rec_d / with_d, 4) if with_d else 0.0,
        }
    return out


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def run(llm: object | None = None, warmup: int = 0) -> tuple[list[SentenceResult], BenchSummary]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Corpus not found at {DATA_PATH}")

    pairs = _load_corpus(DATA_PATH)

    # Warmup: throwaway calls to stabilize the LLM (model load, KV cache).
    # CLAUDE.md §12: always warm up before timing — cold-start artifacts
    # inflated a 135x throughput claim 2026-04-25 incident.
    if warmup > 0 and llm is not None:
        warm_text = strip_diacritics(pairs[0][1])
        for _ in range(warmup):
            fix_diacritics(warm_text, llm=llm)

    results: list[SentenceResult] = []
    start = time.perf_counter()
    for register, sentence in pairs:
        stripped = strip_diacritics(sentence)
        call_start = time.perf_counter()
        if llm is not None:
            restored = fix_diacritics(stripped, llm=llm)
        else:
            restored = fix_diacritics(stripped)
        call_elapsed = time.perf_counter() - call_start
        total, correct, with_d, rec_d = _word_compare(sentence, restored)
        results.append(
            SentenceResult(
                register=register,
                original=sentence,
                stripped=stripped,
                restored=restored,
                word_total=total,
                word_correct=correct,
                word_with_diacritic=with_d,
                word_diacritic_recovered=rec_d,
                latency_seconds=round(call_elapsed, 4),
            )
        )
    elapsed = time.perf_counter() - start

    n_words = sum(r.word_total for r in results)
    n_correct = sum(r.word_correct for r in results)
    n_with_d = sum(r.word_with_diacritic for r in results)
    n_rec_d = sum(r.word_diacritic_recovered for r in results)
    latencies = [r.latency_seconds for r in results]
    mean_lat = sum(latencies) / len(latencies) if latencies else 0.0

    summary = BenchSummary(
        n_sentences=len(results),
        n_words=n_words,
        n_words_with_diacritic=n_with_d,
        overall_word_accuracy=round(n_correct / n_words, 4) if n_words else 0.0,
        overall_diacritic_recall=round(n_rec_d / n_with_d, 4) if n_with_d else 0.0,
        by_register=_aggregate_by_register(results),
        elapsed_seconds=round(elapsed, 4),
        latency_per_sentence_mean=round(mean_lat, 4),
        latency_per_sentence_p50=round(_percentile(latencies, 0.50), 4),
        latency_per_sentence_p95=round(_percentile(latencies, 0.95), 4),
        warmup_calls=warmup,
    )
    return results, summary


def _print_human(summary: BenchSummary, results: list[SentenceResult], show_examples: int) -> None:
    print(f"Corpus: {summary.n_sentences} sentences, {summary.n_words:,} words")
    print(f"Warmup: {summary.warmup_calls} calls · Elapsed: {summary.elapsed_seconds:.3f}s")
    print()
    print(f"{'metric':>30}  {'value':>10}")
    print("-" * 44)
    print(f"{'Overall word accuracy':>30}  {summary.overall_word_accuracy:>10.2%}")
    print(f"{'Overall diacritic recall':>30}  {summary.overall_diacritic_recall:>10.2%}")
    print(f"{'Words with diacritics':>30}  {summary.n_words_with_diacritic:>10,}")
    print(f"{'Latency mean (s/sent)':>30}  {summary.latency_per_sentence_mean:>10.3f}")
    print(f"{'Latency p50 (s/sent)':>30}  {summary.latency_per_sentence_p50:>10.3f}")
    print(f"{'Latency p95 (s/sent)':>30}  {summary.latency_per_sentence_p95:>10.3f}")
    print()
    print("By register:")
    for reg, agg in summary.by_register.items():
        acc = float(agg["word_accuracy"])
        rec = float(agg["diacritic_recall"])
        print(f"  {reg:<28}  {agg['n_sentences']:>3} sents · acc={acc:.2%} · recall={rec:.2%}")

    if show_examples > 0:
        print()
        print(f"Examples (first {show_examples} sentences):")
        for r in results[:show_examples]:
            print(f"  [{r.register}]  acc={r.word_accuracy:.0%} · recall={r.diacritic_recall:.0%}")
            print(f"    GT:        {r.original}")
            print(f"    stripped:  {r.stripped}")
            print(f"    restored:  {r.restored}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Write JSON results to this path")
    parser.add_argument("--examples", type=int, default=3, help="Show N example sentences")
    parser.add_argument(
        "--llm",
        choices=("rule", "ollama", "openai", "anthropic"),
        default="rule",
        help="Restoration backend. 'rule' = built-in lookup table (default); "
        "'ollama'/'openai'/'anthropic' = call the matching nom.llm adapter.",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Override the LLM model (e.g. qwen3:8b for ollama, gpt-4o-mini for openai).",
    )
    parser.add_argument(
        "--ollama-base-url",
        default=None,
        help="Override Ollama server URL (e.g. http://localhost:11435 for an SSH tunnel).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Number of warmup calls before timing (default 3, applies to LLM backends).",
    )
    args = parser.parse_args(argv)

    llm: object | None = None
    if args.llm == "ollama":
        from nom.llm import Ollama

        kwargs: dict[str, str] = {"model": args.llm_model or "qwen3:8b"}
        if args.ollama_base_url:
            kwargs["base_url"] = args.ollama_base_url
        llm = Ollama(**kwargs)
    elif args.llm == "openai":
        from nom.llm import OpenAI

        llm = OpenAI(model=args.llm_model or "gpt-4o-mini") if args.llm_model else OpenAI()
    elif args.llm == "anthropic":
        from nom.llm import Anthropic

        llm = Anthropic(model=args.llm_model) if args.llm_model else Anthropic()

    warmup = args.warmup if llm is not None else 0
    results, summary = run(llm=llm, warmup=warmup)
    _print_human(summary, results, args.examples)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "summary": asdict(summary),
                    "results": [asdict(r) for r in results],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nResults written to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
