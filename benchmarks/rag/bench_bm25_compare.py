"""Compare nom.retrieve.BM25Retriever vs bm25s on the same VN corpus.

Decides whether to swap our pure-Python BM25 default for
[`bm25s`](https://github.com/xhluca/bm25s) (MIT, scipy.sparse).

What we report per implementation:
  - index build time (one-shot cost at construction)
  - per-query search latency (warmup + best-of-N)
  - quality: recall@1 / @3 / @10 + mrr@10 against the fixture's gold

Both implementations use the same Vietnamese tokenizer
(`nom.text.word_tokenize`) so any quality delta comes from the BM25
math + smoothing, not from token differences.

Run::

    python benchmarks/rag/bench_bm25_compare.py \\
        --fixture benchmarks/rag/fixtures/vn_legal_zalo_5k.json \\
        --json benchmarks/results/bm25_compare__zalo_5k.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if (REPO / "src" / "nom" / "__init__.py").exists():
    sys.path.insert(0, str(REPO / "src"))

from nom.chunking import smart_chunk  # noqa: E402
from nom.retrieve import BM25Retriever  # noqa: E402
from nom.text import word_tokenize  # noqa: E402


def _tokenize_vn(s: str) -> list[str]:
    """Vietnamese tokenizer: lowercased compound-aware tokens, alpha+digit only."""
    toks = word_tokenize(s)
    if not isinstance(toks, list):
        toks = list(toks)
    return [t.lower() for t in toks if t.strip()]


def load_fixture(path: Path) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Return (chunks_text, chunk_to_article, questions)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    chunks_text: list[str] = []
    chunk_to_article: list[str] = []
    for art in raw["corpus"]:
        for c in smart_chunk(art["text"], max_tokens=512, overlap=64):
            chunks_text.append(c.text)
            chunk_to_article.append(art["id"])
    return chunks_text, chunk_to_article, raw["questions"]


# ---------------------------------------------------------------------------
# Adapters — uniform interface so the bench treats them identically.
# ---------------------------------------------------------------------------


class NomBM25Adapter:
    name = "nom.retrieve.BM25Retriever"

    def __init__(self, chunks_text: list[str]) -> None:
        self._index_t = time.perf_counter()
        self.r = BM25Retriever.fit(chunks_text)
        self.index_time_s = time.perf_counter() - self._index_t

    def search_indices(self, query: str, k: int) -> list[int]:
        return [h.idx for h in self.r.search(query, top_k=k)]


class BM25SAdapter:
    name = "bm25s"

    def __init__(self, chunks_text: list[str]) -> None:
        import bm25s

        self._index_t = time.perf_counter()
        self.tokens = [_tokenize_vn(t) for t in chunks_text]
        self.r = bm25s.BM25(method="lucene", k1=1.5, b=0.75)
        self.r.index(self.tokens, show_progress=False)
        self.index_time_s = time.perf_counter() - self._index_t

    def search_indices(self, query: str, k: int) -> list[int]:
        q_toks = [_tokenize_vn(query)]
        results, _scores = self.r.retrieve(q_toks, k=k, show_progress=False)
        return [int(i) for i in results[0].tolist()]


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


def recall_at_k(retrieved_articles: list[str], gold: set[str], k: int) -> float:
    return 1.0 if any(a in gold for a in retrieved_articles[:k]) else 0.0


def mrr_at_k(retrieved_articles: list[str], gold: set[str], k: int) -> float:
    for rank, a in enumerate(retrieved_articles[:k], start=1):
        if a in gold:
            return 1.0 / rank
    return 0.0


def hits_to_articles(idxs: list[int], chunk_to_article: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in idxs:
        a = chunk_to_article[i]
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out


def eval_one(
    adapter: Any,
    questions: list[dict[str, Any]],
    chunk_to_article: list[str],
    *,
    top_k: int,
    n_warmup: int,
    n_timed: int,
) -> dict[str, Any]:
    # Quality (deterministic — single pass)
    ks = (1, 3, 5, 10)
    recalls = {k: [] for k in ks}
    mrrs: list[float] = []
    for q in questions:
        gold = set(q["gold_ids"])
        idxs = adapter.search_indices(q["q"], top_k)
        ranked = hits_to_articles(idxs, chunk_to_article)
        for k in ks:
            recalls[k].append(recall_at_k(ranked, gold, k))
        mrrs.append(mrr_at_k(ranked, gold, top_k))

    # Latency (warmup + best-of-N)
    for _ in range(n_warmup):
        for q in questions:
            adapter.search_indices(q["q"], top_k)

    pass_p50: list[float] = []
    pass_p95: list[float] = []
    for _ in range(n_timed):
        per_q: list[float] = []
        for q in questions:
            t0 = time.perf_counter()
            adapter.search_indices(q["q"], top_k)
            per_q.append((time.perf_counter() - t0) * 1000.0)
        per_q.sort()
        pass_p50.append(per_q[len(per_q) // 2])
        pass_p95.append(per_q[max(0, int(len(per_q) * 0.95) - 1)])

    return {
        "name": adapter.name,
        "index_time_s": round(adapter.index_time_s, 2),
        **{f"recall@{k}": round(statistics.mean(recalls[k]), 4) for k in ks},
        "mrr@10": round(statistics.mean(mrrs), 4),
        "p50_ms": round(min(pass_p50), 3),
        "p95_ms": round(min(pass_p95), 3),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--n-warmup", type=int, default=1)
    p.add_argument("--n-timed", type=int, default=2)
    p.add_argument("--json", type=Path, default=None)
    args = p.parse_args(argv)

    chunks_text, chunk_to_article, questions = load_fixture(args.fixture)
    print(f"fixture: {args.fixture.name}  chunks={len(chunks_text)}  questions={len(questions)}")

    print(f"\nbuilding {NomBM25Adapter.name}...")
    nom_a = NomBM25Adapter(chunks_text)
    print(f"  indexed in {nom_a.index_time_s:.2f}s")

    print(f"building {BM25SAdapter.name}...")
    bm25s_a = BM25SAdapter(chunks_text)
    print(f"  indexed in {bm25s_a.index_time_s:.2f}s")

    print("\nevaluating...")
    rows = []
    for adapter in (nom_a, bm25s_a):
        rows.append(
            eval_one(
                adapter,
                questions,
                chunk_to_article,
                top_k=args.top_k,
                n_warmup=args.n_warmup,
                n_timed=args.n_timed,
            )
        )

    cols = ["recall@1", "recall@3", "recall@10", "mrr@10", "index_time_s", "p50_ms", "p95_ms"]
    name_w = max(8, max(len(r["name"]) for r in rows))
    print()
    print("Engine".ljust(name_w) + "  " + "  ".join(c.rjust(13) for c in cols))
    print("-" * (name_w + 2 + 15 * len(cols)))
    for r in rows:
        cells = [
            f"{r['recall@1']:.4f}",
            f"{r['recall@3']:.4f}",
            f"{r['recall@10']:.4f}",
            f"{r['mrr@10']:.4f}",
            f"{r['index_time_s']:.2f}",
            f"{r['p50_ms']:.3f}",
            f"{r['p95_ms']:.3f}",
        ]
        print(r["name"].ljust(name_w) + "  " + "  ".join(c.rjust(13) for c in cells))
    print()

    result = {
        "config": {
            "fixture": args.fixture.name,
            "n_chunks": len(chunks_text),
            "n_questions": len(questions),
            "top_k": args.top_k,
            "n_warmup": args.n_warmup,
            "n_timed": args.n_timed,
        },
        "engines": {r["name"]: r for r in rows},
        "meta": {
            "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version.split()[0],
        },
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"→ wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
