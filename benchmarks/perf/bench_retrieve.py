"""Performance benchmark for ``nom.retrieve``.

Measures index build + query latency for BM25 and Dense retrievers
over a synthetic VN corpus, plus hybrid score-fusion overhead.

Methodology (per CLAUDE.md principle 12):
- Warmup: 3 runs over the corpus before timing.
- Best-of-5 over the corpus.
- Reports: index build time, single-query latency p50/p95, throughput.

Run::

    python benchmarks/perf/bench_retrieve.py
    python benchmarks/perf/bench_retrieve.py --json results/retrieve.json
    python benchmarks/perf/bench_retrieve.py --n-docs 10000  # bigger corpus
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from nom.retrieve import BM25Retriever, DenseRetriever, hybrid_score

_BASE_SENTENCES = [
    "Hợp đồng số {n}/HĐ/2025 được lập ngày 14 tháng 3 năm 2025.",
    "Bên A: Công ty Cổ phần Hồng Hà số {n}, mã số thuế 0123456789.",
    "Tổng giá trị hợp đồng là {n} triệu đồng.",
    "Công văn số {n} ban hành ngày 1 tháng 4 năm 2025.",
    "Đơn xin nghỉ việc của ông Văn {n} từ tháng 5 năm 2025.",
    "Thời hạn thực hiện sáu tháng kể từ ngày ký kết hợp đồng số {n}.",
    "Đại học Quốc gia thành phố Hồ Chí Minh tuyển sinh đợt {n}.",
    "Triển lãm mỹ thuật quốc tế lần thứ {n} khai mạc tại Hà Nội.",
]


def _make_corpus(n_docs: int) -> list[str]:
    """Build a corpus of n_docs synthetic VN documents."""
    return [_BASE_SENTENCES[i % len(_BASE_SENTENCES)].format(n=i) for i in range(n_docs)]


def _random_normalized_embeddings(n: int, d: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    m = rng.standard_normal((n, d), dtype="float32")
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


@dataclass
class BenchResult:
    n_docs: int
    bm25_build_ms: float
    bm25_query_p50_ms: float
    bm25_query_p95_ms: float
    bm25_qps: float
    dense_query_p50_ms: float
    dense_query_p95_ms: float
    dense_qps: float
    rrf_fusion_p50_ms: float
    rrf_fusion_qps: float


def _percentiles(values: list[float]) -> tuple[float, float]:
    p50 = statistics.median(values)
    p95 = sorted(values)[int(len(values) * 0.95)]
    return p50, p95


def _bench_query(
    fn, queries: list, *, warmup: int = 3, runs: int = 200
) -> tuple[float, float, float]:
    """Returns (p50_ms, p95_ms, qps)."""
    # Warmup
    for q in queries[:warmup]:
        fn(q)
    timings_ms: list[float] = []
    for q in queries[:runs]:
        start = time.perf_counter()
        fn(q)
        timings_ms.append((time.perf_counter() - start) * 1000)
    p50, p95 = _percentiles(timings_ms)
    qps = 1000.0 / p50 if p50 > 0 else 0.0
    return p50, p95, qps


def run(n_docs: int = 1000) -> BenchResult:
    corpus = _make_corpus(n_docs)

    # --- BM25: index build ---
    bm25_build_start = time.perf_counter()
    bm25 = BM25Retriever.fit(corpus)
    bm25_build_ms = (time.perf_counter() - bm25_build_start) * 1000

    # 200 distinct queries (cycle through likely terms)
    queries = [f"hợp đồng số {i}" for i in range(50)] + [
        "công văn",
        "đại học",
        "triển lãm",
        "đơn xin",
        "tổng giá trị",
        "Hà Nội",
        "Hồ Chí Minh",
        "Bên A",
        "công ty",
        "thời hạn",
    ] * 15

    # --- BM25: query ---
    bm25_p50, bm25_p95, bm25_qps = _bench_query(lambda q: bm25.search(q, top_k=10), queries)

    # --- Dense: index build (just construction) + query ---
    dim = 768  # match VietnameseEmbedder default
    embeddings = _random_normalized_embeddings(n_docs, dim)
    dense = DenseRetriever(embeddings, documents=corpus)

    query_vecs = _random_normalized_embeddings(200, dim, seed=99)
    dense_p50, dense_p95, dense_qps = _bench_query(
        lambda v: dense.search(v, top_k=10),
        [query_vecs[i] for i in range(200)],
    )

    # --- Hybrid RRF: fuse BM25 + Dense top-10 lists ---
    bm25_hits = bm25.search("hợp đồng", top_k=10)
    dense_hits = dense.search(query_vecs[0], top_k=10)

    rrf_p50, _rrf_p95, rrf_qps = _bench_query(
        lambda _: hybrid_score([bm25_hits, dense_hits], method="rrf", top_k=10),
        list(range(200)),
    )

    return BenchResult(
        n_docs=n_docs,
        bm25_build_ms=round(bm25_build_ms, 1),
        bm25_query_p50_ms=round(bm25_p50, 3),
        bm25_query_p95_ms=round(bm25_p95, 3),
        bm25_qps=round(bm25_qps, 0),
        dense_query_p50_ms=round(dense_p50, 3),
        dense_query_p95_ms=round(dense_p95, 3),
        dense_qps=round(dense_qps, 0),
        rrf_fusion_p50_ms=round(rrf_p50, 3),
        rrf_fusion_qps=round(rrf_qps, 0),
    )


def _print_human(r: BenchResult) -> None:
    print(f"Corpus: {r.n_docs:,} synthetic VN docs")
    print("Methodology: warmup x 3, p50/p95 over 200 queries each.")
    print()
    print(f"{'metric':>32}  {'value':>14}")
    print("-" * 50)
    print(f"{'BM25 build':>32}  {r.bm25_build_ms:>11.1f} ms")
    print(f"{'BM25 query p50':>32}  {r.bm25_query_p50_ms:>11.3f} ms")
    print(f"{'BM25 query p95':>32}  {r.bm25_query_p95_ms:>11.3f} ms")
    print(f"{'BM25 throughput':>32}  {r.bm25_qps:>10,.0f} qps")
    print(f"{'Dense query p50 (768-dim)':>32}  {r.dense_query_p50_ms:>11.3f} ms")
    print(f"{'Dense query p95':>32}  {r.dense_query_p95_ms:>11.3f} ms")
    print(f"{'Dense throughput':>32}  {r.dense_qps:>10,.0f} qps")
    print(f"{'RRF fusion p50':>32}  {r.rrf_fusion_p50_ms:>11.3f} ms")
    print(f"{'RRF fusion throughput':>32}  {r.rrf_fusion_qps:>10,.0f} qps")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-docs", type=int, default=1000, help="Corpus size (default 1000)")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    result = run(n_docs=args.n_docs)
    _print_human(result)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2)
        print(f"\nResults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
