"""Performance benchmark for ``nom.embeddings.VietnameseEmbedder``.

**Manual / opt-in.** Downloads ~440 MB of model weights on first run.
Skipped automatically when ``sentence-transformers`` is not installed
(prints an install hint).

Methodology (per CLAUDE.md principle 12):
- **Cold start** is reported separately — it's the first call after
  ``__init__`` and includes model load. We do NOT amortize it into the
  steady-state numbers (history of nom-vn already showed this artifact
  inflates ratios; see commit ``df344f0``).
- **Warmup**: 5 single-call encodes after the cold start.
- **Steady state**: best-of-3 runs over the corpus.
- Reports: cold-start latency, warm single-call p50, batch throughput
  at multiple batch sizes, vector dim, model name.

Run::

    python benchmarks/perf/bench_embeddings.py
    python benchmarks/perf/bench_embeddings.py --json results/embeddings.json
    python benchmarks/perf/bench_embeddings.py --model paraphrase-multilingual-MiniLM-L12-v2
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# Realistic VN snippets (mix of contract / news / conversational) — same shape
# users hit in retrieve workloads.
_CORPUS = [
    "Hợp đồng số 02/HĐ/2025 được lập ngày 14 tháng 3 năm 2025.",
    "Bên A: Công ty Cổ phần Hồng Hà, mã số thuế 0123456789.",
    "Tổng giá trị hợp đồng là một tỷ năm trăm triệu đồng chẵn.",
    "Hôm nay trời mưa to, anh có cần tôi đem ô đến không?",
    "Đại học Quốc gia thành phố Hồ Chí Minh tuyển sinh đại trà từ tháng ba.",
    "Kính gửi Quý Sở Lao động Thương binh và Xã hội thành phố.",
    "Đơn xin nghỉ việc không hưởng lương trong thời gian một tháng.",
    "Năm nay là dịp kỷ niệm năm mươi năm ngày thống nhất đất nước.",
    "Doanh nghiệp công nghệ Việt Nam đẩy mạnh xuất khẩu phần mềm sang Nhật.",
    "Triển lãm mỹ thuật quốc tế khai mạc tại Bảo tàng Mỹ thuật Hà Nội.",
] * 10  # 100 sentences total


@dataclass
class BenchResult:
    model: str
    dim: int
    cold_start_seconds: float
    warm_p50_ms: float
    warm_p95_ms: float
    batch_8_throughput_per_sec: float
    batch_32_throughput_per_sec: float
    batch_128_throughput_per_sec: float
    n_corpus: int


def _check_sentence_transformers() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        print(
            "ERROR: sentence-transformers not installed. Install with:",
            file=sys.stderr,
        )
        print("    pip install nom-vn[embeddings]", file=sys.stderr)
        return False


def _bench_batch(embedder, texts: list[str], batch_size: int, runs: int = 3) -> float:
    """Best-of-N throughput in texts/sec at the given batch_size."""
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        embedder.embed_batch(texts, batch_size=batch_size)
        elapsed = time.perf_counter() - start
        if elapsed < best:
            best = elapsed
    return len(texts) / best


def run(model_name: str | None = None) -> BenchResult:
    from nom.embeddings import VietnameseEmbedder

    embedder = VietnameseEmbedder(model_name) if model_name else VietnameseEmbedder()

    # Cold start: first call includes model load.
    cold_start = time.perf_counter()
    _ = embedder.embed("warmup")
    cold_elapsed = time.perf_counter() - cold_start

    # Warmup: 5 single-call encodes
    for _ in range(5):
        embedder.embed("Hợp đồng số 02")

    # Single-call latency distribution (50 calls)
    single_call_ms: list[float] = []
    for _ in range(50):
        start = time.perf_counter()
        embedder.embed("Hợp đồng số 02 được lập ngày 14 tháng 3 năm 2025.")
        single_call_ms.append((time.perf_counter() - start) * 1000)

    p50 = statistics.median(single_call_ms)
    p95 = sorted(single_call_ms)[int(len(single_call_ms) * 0.95)]

    # Batch throughput at three sizes
    bs8 = _bench_batch(embedder, _CORPUS, batch_size=8)
    bs32 = _bench_batch(embedder, _CORPUS, batch_size=32)
    bs128 = _bench_batch(embedder, _CORPUS, batch_size=128)

    return BenchResult(
        model=embedder.name,
        dim=embedder.dim,
        cold_start_seconds=round(cold_elapsed, 3),
        warm_p50_ms=round(p50, 3),
        warm_p95_ms=round(p95, 3),
        batch_8_throughput_per_sec=round(bs8, 1),
        batch_32_throughput_per_sec=round(bs32, 1),
        batch_128_throughput_per_sec=round(bs128, 1),
        n_corpus=len(_CORPUS),
    )


def _print_human(r: BenchResult) -> None:
    print(f"Model:          {r.model}")
    print(f"Dim:            {r.dim}")
    print(f"Corpus size:    {r.n_corpus} VN sentences")
    print()
    print(f"{'metric':>34}  {'value':>15}")
    print("-" * 52)
    print(f"{'cold-start (incl. model load)':>34}  {r.cold_start_seconds:>13.2f} s")
    print(f"{'warm single-call p50':>34}  {r.warm_p50_ms:>11.2f} ms")
    print(f"{'warm single-call p95':>34}  {r.warm_p95_ms:>11.2f} ms")
    print(f"{'batch (size=8) throughput':>34}  {r.batch_8_throughput_per_sec:>10.1f} txt/s")
    print(f"{'batch (size=32) throughput':>34}  {r.batch_32_throughput_per_sec:>10.1f} txt/s")
    print(f"{'batch (size=128) throughput':>34}  {r.batch_128_throughput_per_sec:>10.1f} txt/s")


def main(argv: list[str] | None = None) -> int:
    if not _check_sentence_transformers():
        return 1

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", help="HuggingFace model id (default: VietnameseEmbedder default)"
    )
    parser.add_argument("--json", type=Path, default=None, help="Write JSON results")
    args = parser.parse_args(argv)

    print(
        "Note: first run downloads model weights to ~/.cache/huggingface (~440 MB for default).\n"
    )

    result = run(args.model)
    _print_human(result)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2)
        print(f"\nResults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
