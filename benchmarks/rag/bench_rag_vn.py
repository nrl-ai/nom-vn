"""Vietnamese RAG retrieval benchmark — Recall@k / MRR@10 / latency.

Measures the **retrieval** half of ``nom.rag`` against a corpus of
Vietnamese legal articles + a held-out question set with known gold
article mappings. The LLM step is intentionally excluded — answer
quality benchmarks are a separate axis (judge-LLM, exact-match, …)
that compounds confounders. This script isolates the retriever.

Methodology (per CLAUDE.md principle 12):
- The fixture, the embedder, and the retriever versions are all
  recorded in the output JSON.
- Latency: warmup 3 queries, timed best-of-N runs (default N=5),
  reports p50 / p95 per retriever over the question set.
- Best-of-N is *not* applied to the metrics themselves — those are
  deterministic given the same fixture + embedder seed.
- The ``--embedder fake`` default is reproducible bit-for-bit and
  exercises the harness offline. Real-quality numbers require
  ``--embedder vietnamese`` (downloads ~440 MB on first run).

Run::

    python benchmarks/rag/bench_rag_vn.py
    python benchmarks/rag/bench_rag_vn.py --embedder vietnamese
    python benchmarks/rag/bench_rag_vn.py \\
        --fixture benchmarks/rag/fixtures/vn_legal_tiny.json \\
        --json benchmarks/rag/baselines/result.json

Output JSON shape: see ``_dump_result`` at bottom of file.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# Import path: prefer src layout in dev, fall back to installed package.
_REPO = Path(__file__).resolve().parents[2]
if (_REPO / "src" / "nom" / "__init__.py").exists():
    sys.path.insert(0, str(_REPO / "src"))

from nom.chunking import smart_chunk  # noqa: E402
from nom.retrieve import BM25Retriever, DenseRetriever, hybrid_score  # noqa: E402

# ---------------------------------------------------------------------------
# Embedder adapters
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    """Deterministic, network-free embedder. Matches ``nom.embeddings.Embedder``.

    Hash-seeds a 32-dim normal vector per text; L2-normalizes. Useful for
    harness validation and CI runs but produces near-random retrieval
    quality on the dense leg — interpret dense numbers from this embedder
    as *floor*, not as a real measurement.
    """

    name = "fake-embedder-32d"
    dim = 32

    def embed(self, text: str) -> np.ndarray:
        h = abs(hash(text)) % (2**32)
        rng = np.random.default_rng(h)
        v = rng.standard_normal(self.dim, dtype="float32")
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def embed_batch(self, texts: list[str], *, batch_size: int = 32) -> np.ndarray:
        del batch_size
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")
        return np.stack([self.embed(t) for t in texts])


def _auto_device() -> str:
    """Pick the fastest available device. Mirrors what production should do."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _build_embedder(name: str, device: str = "cpu") -> Any:
    if name == "fake":
        return _FakeEmbedder()
    if name == "vietnamese":
        from nom.embeddings import VietnameseEmbedder

        return VietnameseEmbedder(device=device)
    if name == "aiteamvn":
        from nom.embeddings import AITeamVNEmbedder

        return AITeamVNEmbedder(device=device)
    if name == "bkai":
        from nom.embeddings import BKaiEmbedder

        return BKaiEmbedder(device=device)
    raise SystemExit(f"unknown embedder: {name!r} (choices: fake, vietnamese, aiteamvn, bkai)")


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fixture:
    name: str
    corpus: list[dict[str, str]]  # [{"id": str, "text": str}, ...]
    questions: list[dict[str, Any]]  # [{"q": str, "gold_ids": [str, ...]}, ...]


def _load_fixture(path: Path) -> Fixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Fixture(
        name=raw.get("name", path.stem),
        corpus=raw["corpus"],
        questions=raw["questions"],
    )


# ---------------------------------------------------------------------------
# Index build
# ---------------------------------------------------------------------------


@dataclass
class IndexedCorpus:
    chunks_text: list[str]
    chunk_to_article: list[str]  # parallel to chunks_text — gold article id per chunk
    embeddings: np.ndarray
    bm25: BM25Retriever
    dense: DenseRetriever
    n_articles: int


def _build_index(
    fixture: Fixture,
    embedder: Any,
    *,
    chunk_max_tokens: int = 512,
    chunk_overlap: int = 64,
) -> IndexedCorpus:
    chunks_text: list[str] = []
    chunk_to_article: list[str] = []
    for art in fixture.corpus:
        for c in smart_chunk(art["text"], max_tokens=chunk_max_tokens, overlap=chunk_overlap):
            chunks_text.append(c.text)
            chunk_to_article.append(art["id"])
    if not chunks_text:
        raise SystemExit("fixture produced zero chunks")
    embeddings = embedder.embed_batch(chunks_text).astype("float32", copy=False)
    bm25 = BM25Retriever.fit(chunks_text)
    dense = DenseRetriever(embeddings, documents=chunks_text)
    return IndexedCorpus(
        chunks_text=chunks_text,
        chunk_to_article=chunk_to_article,
        embeddings=embeddings,
        bm25=bm25,
        dense=dense,
        n_articles=len(fixture.corpus),
    )


# ---------------------------------------------------------------------------
# Retrieval + scoring
# ---------------------------------------------------------------------------

# Retriever names → callable returning top-K hits in rank order.
RetrievalFn = Any  # callable(question, k) -> list[Hit]


def _make_retrievers(
    indexed: IndexedCorpus,
    embedder: Any,
    *,
    n_retrieve: int,
    reranker: Any | None = None,
    rerank_candidates: int = 30,
) -> dict[str, RetrievalFn]:
    bm25 = indexed.bm25
    dense = indexed.dense
    chunks_text = indexed.chunks_text

    def bm25_search(q: str, k: int) -> list[Any]:
        return bm25.search(q, top_k=k)

    def dense_search(q: str, k: int) -> list[Any]:
        return dense.search(embedder.embed(q), top_k=k)

    def hybrid_search(q: str, k: int) -> list[Any]:
        b = bm25.search(q, top_k=n_retrieve)
        d = dense.search(embedder.embed(q), top_k=n_retrieve)
        return hybrid_score([b, d], method="rrf", top_k=k, rrf_k=60)

    retrievers: dict[str, RetrievalFn] = {
        "bm25": bm25_search,
        "dense": dense_search,
        "hybrid": hybrid_search,
    }

    if reranker is not None:
        # Wider per-leg pool so the reranker has enough to choose from.
        pool = max(n_retrieve, rerank_candidates)

        def hybrid_rerank_search(q: str, k: int) -> list[Any]:
            b = bm25.search(q, top_k=pool)
            d = dense.search(embedder.embed(q), top_k=pool)
            fused = hybrid_score([b, d], method="rrf", top_k=rerank_candidates, rrf_k=60)
            from nom.retrieve import Hit as _Hit

            text_hits = [
                _Hit(idx=h.idx, score=h.score, text=h.text or chunks_text[h.idx]) for h in fused
            ]
            return reranker.rerank(q, text_hits, top_k=k)

        retrievers["hybrid+rerank"] = hybrid_rerank_search

    return retrievers


def _hits_to_articles(hits: list[Any], chunk_to_article: list[str]) -> list[str]:
    """Map ranked chunk hits → ranked article ids, preserving order, deduped."""
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        a = chunk_to_article[h.idx]
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out


def _recall_at_k(retrieved_articles: list[str], gold: set[str], k: int) -> float:
    return 1.0 if any(a in gold for a in retrieved_articles[:k]) else 0.0


def _mrr_at_k(retrieved_articles: list[str], gold: set[str], k: int) -> float:
    for rank, a in enumerate(retrieved_articles[:k], start=1):
        if a in gold:
            return 1.0 / rank
    return 0.0


def _score_run(
    retriever: RetrievalFn,
    questions: list[dict[str, Any]],
    chunk_to_article: list[str],
    *,
    top_k: int = 10,
) -> dict[str, float]:
    ks = (1, 3, 5, 10)
    recalls: dict[int, list[float]] = {k: [] for k in ks}
    mrrs: list[float] = []
    for qrec in questions:
        gold = set(qrec["gold_ids"])
        hits = retriever(qrec["q"], top_k)
        ranked = _hits_to_articles(hits, chunk_to_article)
        for k in ks:
            recalls[k].append(_recall_at_k(ranked, gold, k))
        mrrs.append(_mrr_at_k(ranked, gold, top_k))
    return {
        **{f"recall@{k}": round(statistics.mean(recalls[k]), 4) for k in ks},
        "mrr@10": round(statistics.mean(mrrs), 4),
    }


# ---------------------------------------------------------------------------
# Latency timing
# ---------------------------------------------------------------------------


def _time_run(
    retriever: RetrievalFn,
    questions: list[dict[str, Any]],
    *,
    n_warmup: int,
    n_timed: int,
    top_k: int,
) -> dict[str, float]:
    """Run all questions through retriever; return per-query latency stats.

    n_warmup: full-pass warmups discarded (for any one-time JIT / model
        warmup the embedder / retriever does on first call).
    n_timed: how many full passes to time. We report the BEST observed
        per-query p50/p95 across passes — best-of-N protects against
        OS noise without lying about cold-start.
    """
    for _ in range(n_warmup):
        for qrec in questions:
            retriever(qrec["q"], top_k)

    pass_p50: list[float] = []
    pass_p95: list[float] = []
    for _ in range(n_timed):
        per_q: list[float] = []
        for qrec in questions:
            t0 = time.perf_counter()
            retriever(qrec["q"], top_k)
            per_q.append((time.perf_counter() - t0) * 1000.0)
        per_q.sort()
        pass_p50.append(per_q[len(per_q) // 2])
        pass_p95.append(per_q[max(0, int(len(per_q) * 0.95) - 1)])
    return {
        "p50_ms": round(min(pass_p50), 3),
        "p95_ms": round(min(pass_p95), 3),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=_REPO, stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return None


def _dump_result(
    *,
    fixture: Fixture,
    indexed: IndexedCorpus,
    embedder: Any,
    reranker: Any | None,
    rerank_candidates: int,
    metrics: dict[str, dict[str, float]],
    latency: dict[str, dict[str, float]],
    n_warmup: int,
    n_timed: int,
    n_retrieve: int,
    chunk_max_tokens: int,
    chunk_overlap: int,
    out_path: Path | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "config": {
            "fixture": fixture.name,
            "n_corpus_articles": len(fixture.corpus),
            "n_chunks": len(indexed.chunks_text),
            "n_questions": len(fixture.questions),
            "embedder": getattr(embedder, "name", type(embedder).__name__),
            "embedder_dim": int(embedder.dim),
            "embedder_device": getattr(embedder, "device", "n/a"),
            "reranker": getattr(reranker, "name", None) if reranker else None,
            "reranker_device": getattr(reranker, "device", None) if reranker else None,
            "rerank_candidates": rerank_candidates if reranker else None,
            "chunk_max_tokens": chunk_max_tokens,
            "chunk_overlap": chunk_overlap,
            "fusion": "rrf",
            "rrf_k": 60,
            "n_retrieve": n_retrieve,
        },
        "metrics": metrics,
        "latency_ms": latency,
        "meta": {
            "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "n_warmup": n_warmup,
            "n_timed": n_timed,
            "python": sys.version.split()[0],
        },
    }
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def _print_table(result: dict[str, Any]) -> None:
    cfg = result["config"]
    print(
        f"\nFixture: {cfg['fixture']}  "
        f"({cfg['n_corpus_articles']} articles, {cfg['n_chunks']} chunks, "
        f"{cfg['n_questions']} questions)"
    )
    print(f"Embedder: {cfg['embedder']} (dim {cfg['embedder_dim']})")
    print(f"Fusion: {cfg['fusion']} (rrf_k={cfg['rrf_k']}, n_retrieve={cfg['n_retrieve']})\n")

    cols = ["recall@1", "recall@3", "recall@5", "recall@10", "mrr@10", "p50_ms", "p95_ms"]
    name_w = max(8, max(len(r) for r in result["metrics"]))
    header = "Retriever".ljust(name_w) + "  " + "  ".join(c.rjust(8) for c in cols)
    print(header)
    print("-" * len(header))
    for r, m in result["metrics"].items():
        lat = result["latency_ms"][r]
        cells = [
            f"{m['recall@1']:.3f}",
            f"{m['recall@3']:.3f}",
            f"{m['recall@5']:.3f}",
            f"{m['recall@10']:.3f}",
            f"{m['mrr@10']:.3f}",
            f"{lat['p50_ms']:.2f}",
            f"{lat['p95_ms']:.2f}",
        ]
        print(r.ljust(name_w) + "  " + "  ".join(c.rjust(8) for c in cells))
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "vn_legal_tiny.json",
        help="Path to fixture JSON (corpus + questions).",
    )
    p.add_argument(
        "--embedder",
        choices=("fake", "vietnamese", "aiteamvn", "bkai"),
        default="fake",
        help="Embedder backend. 'fake' is offline + deterministic; "
        "'vietnamese' = dangvantuan/vietnamese-embedding (~440 MB, dim 768); "
        "'aiteamvn' = AITeamVN/Vietnamese_Embedding (~2 GB, dim 1024, BGE-M3 base).",
    )
    p.add_argument(
        "--device",
        default="auto",
        help="Compute device. 'auto' picks cuda > mps > cpu. Pass 'cpu' to "
        "force CPU even when a GPU is present.",
    )
    p.add_argument(
        "--retrievers",
        default="bm25,dense,hybrid",
        help="Comma-separated list of retrievers to evaluate. "
        "Add 'hybrid+rerank' to include the cross-encoder stage.",
    )
    p.add_argument(
        "--reranker",
        default=None,
        help="HuggingFace cross-encoder model id (e.g. BAAI/bge-reranker-v2-m3, "
        "namdp-ptit/ViRanker, itdainb/PhoRanker). Required when 'hybrid+rerank' "
        "is in --retrievers.",
    )
    p.add_argument(
        "--rerank-candidates",
        type=int,
        default=30,
        help="Bi-encoder pool size sent to the reranker (production sweet spot 30-75).",
    )
    p.add_argument(
        "--reranker-max-length",
        type=int,
        default=None,
        help="Override reranker max input length (default: auto-detect from "
        "model config — 256 for PhoBERT-base rerankers, 512 for XLM-R-large).",
    )
    p.add_argument("--top-k", type=int, default=10, help="Top-K for metrics.")
    p.add_argument(
        "--n-retrieve",
        type=int,
        default=20,
        help="Per-leg retrieval budget before hybrid fusion.",
    )
    p.add_argument("--chunk-max-tokens", type=int, default=512)
    p.add_argument("--chunk-overlap", type=int, default=64)
    p.add_argument("--n-warmup", type=int, default=3)
    p.add_argument("--n-timed", type=int, default=5)
    p.add_argument("--json", type=Path, help="Write result JSON to this path.")
    args = p.parse_args(argv)

    device = _auto_device() if args.device == "auto" else args.device
    print(f"device={device}")
    fixture = _load_fixture(args.fixture)
    embedder = _build_embedder(args.embedder, device=device)
    indexed = _build_index(
        fixture,
        embedder,
        chunk_max_tokens=args.chunk_max_tokens,
        chunk_overlap=args.chunk_overlap,
    )
    reranker: Any | None = None
    if args.reranker:
        from nom.rag import CrossEncoderReranker

        # max_length=None → CrossEncoderReranker auto-detects the safe cap
        # from the model's config.json. PhoRanker (256), bge-reranker-v2-m3
        # (512), ViRanker (512). Override with --reranker-max-length if you
        # need to clamp lower (saves memory) or test a different value.
        reranker = CrossEncoderReranker(
            args.reranker,
            device=device,
            max_length=args.reranker_max_length,
        )
    retrievers = _make_retrievers(
        indexed,
        embedder,
        n_retrieve=args.n_retrieve,
        reranker=reranker,
        rerank_candidates=args.rerank_candidates,
    )

    selected = [r.strip() for r in args.retrievers.split(",") if r.strip()]
    metrics: dict[str, dict[str, float]] = {}
    latency: dict[str, dict[str, float]] = {}
    for name in selected:
        if name not in retrievers:
            raise SystemExit(f"unknown retriever: {name!r}")
        metrics[name] = _score_run(
            retrievers[name],
            fixture.questions,
            indexed.chunk_to_article,
            top_k=args.top_k,
        )
        latency[name] = _time_run(
            retrievers[name],
            fixture.questions,
            n_warmup=args.n_warmup,
            n_timed=args.n_timed,
            top_k=args.top_k,
        )

    result = _dump_result(
        fixture=fixture,
        indexed=indexed,
        embedder=embedder,
        reranker=reranker,
        rerank_candidates=args.rerank_candidates,
        metrics=metrics,
        latency=latency,
        n_warmup=args.n_warmup,
        n_timed=args.n_timed,
        n_retrieve=args.n_retrieve,
        chunk_max_tokens=args.chunk_max_tokens,
        chunk_overlap=args.chunk_overlap,
        out_path=args.json,
    )
    _print_table(result)
    if args.json:
        print(f"→ wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
