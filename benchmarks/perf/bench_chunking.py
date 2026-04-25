"""Performance benchmark for ``nom.chunking``.

Measures throughput on a realistic VN-document corpus across the three
boundary modes (sentence / paragraph / character).

Methodology (per CLAUDE.md principle 12):
- Warmup: 3 calls over the full corpus before timing.
- Best-of-5 over 5 runs.
- Reports docs/sec, chunks/sec, and chars/sec.

Run::

    python benchmarks/perf/bench_chunking.py
    python benchmarks/perf/bench_chunking.py --json results/chunking.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from nom.chunking import BoundaryMode, smart_chunk

REPO_ROOT = Path(__file__).resolve().parents[2]


# Realistic synthetic corpus — multiple registers, varying lengths.
_PARAGRAPH = """\
Hợp đồng số {n}/HĐ/2025 được lập ngày 14 tháng 3 năm 2025 tại văn phòng công ty.
Bên A: Công ty Cổ phần Hồng Hà, mã số thuế 0123456789, địa chỉ Hà Nội.
Bên B: Bà Nguyễn Thị Hương, sinh năm 1990, CMND số 012345678901.
Tổng giá trị hợp đồng: 1.500.000.000 đồng (một tỷ năm trăm triệu đồng chẵn).
Điều 1. Đối tượng hợp đồng: triển khai hệ thống chatbot tiếng Việt.
Điều 2. Thời hạn thực hiện: 6 tháng kể từ ngày ký kết.
Điều 3. Phương thức thanh toán: chuyển khoản, chia làm 3 đợt.
Điều 4. Quyền và nghĩa vụ các bên thực hiện theo quy định pháp luật hiện hành."""


def _make_corpus(n_docs: int = 50) -> list[str]:
    """Build a corpus of n_docs synthetic VN documents (~5KB each)."""
    return ["\n\n".join([_PARAGRAPH.format(n=i) for i in range(8)]) for _ in range(n_docs)]


def _bench(
    label: str,
    fn,
    corpus: list[str],
    *,
    runs: int = 5,
    warmup: int = 3,
) -> tuple[float, int, int]:
    """Returns (best_seconds, total_chunks, total_chars)."""
    # Warmup
    for _ in range(warmup):
        for d in corpus[: min(5, len(corpus))]:
            fn(d)
    best = float("inf")
    total_chunks = 0
    total_chars = sum(len(d) for d in corpus)
    for _ in range(runs):
        start = time.perf_counter()
        for d in corpus:
            chunks = fn(d)
            total_chunks = len(chunks) * len(corpus)  # last run determines count
        elapsed = time.perf_counter() - start
        if elapsed < best:
            best = elapsed
    return best, total_chunks, total_chars


@dataclass
class ModeResult:
    mode: str
    best_seconds: float
    docs_per_sec: float
    chars_per_sec: float
    avg_chunks_per_doc: float


def run() -> list[ModeResult]:
    corpus = _make_corpus(n_docs=50)
    results: list[ModeResult] = []

    for mode in (BoundaryMode.SENTENCE, BoundaryMode.PARAGRAPH, BoundaryMode.CHARACTER):

        def chunk_fn(text: str, _m: BoundaryMode = mode) -> list:
            return smart_chunk(text, max_tokens=512, overlap=64, boundary=_m)

        best, _last_chunks, total_chars = _bench(mode.value, chunk_fn, corpus)
        # Recompute chunk count from one run for honest avg.
        sample_chunks = sum(len(chunk_fn(d)) for d in corpus)
        results.append(
            ModeResult(
                mode=mode.value,
                best_seconds=round(best, 4),
                docs_per_sec=round(len(corpus) / best, 1),
                chars_per_sec=round(total_chars / best, 0),
                avg_chunks_per_doc=round(sample_chunks / len(corpus), 2),
            )
        )
    return results


def _print_human(results: list[ModeResult]) -> None:
    n_docs = 50
    avg_doc_size = sum(len(d) for d in _make_corpus(n_docs)) // n_docs
    print(f"Corpus: {n_docs} synthetic VN docs (~{avg_doc_size:,} chars each)")
    print("Methodology: warmup x 3 calls, best-of-5 runs.")
    print()
    print(f"{'mode':>11}  {'time':>10}  {'docs/sec':>10}  {'chars/sec':>14}  {'chunks/doc':>11}")
    print("-" * 64)
    for r in results:
        print(
            f"{r.mode:>11}  "
            f"{r.best_seconds * 1000:>7.1f} ms  "
            f"{r.docs_per_sec:>10.1f}  "
            f"{r.chars_per_sec:>14,.0f}  "
            f"{r.avg_chunks_per_doc:>11.2f}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Write JSON results")
    args = parser.parse_args(argv)

    results = run()
    _print_human(results)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        print(f"\nResults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
