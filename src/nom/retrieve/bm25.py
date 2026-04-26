"""Okapi BM25 over Vietnamese-tokenized text.

Implementation notes:

- **VN-aware tokenization.** Documents and queries flow through
  ``nom.text.word_tokenize`` so compound words (``"Hợp đồng"``,
  ``"thành phố Hồ Chí Minh"``) count as single terms — matches the
  way humans index VN docs.
- **Backed by `bm25s`** (MIT, scipy.sparse) for the math. We measured
  the swap on the full Zalo Legal QA corpus (82k chunks, 788 queries):
  bit-identical recall@1/@10 vs the previous pure-Python implementation,
  and **search latency dropped from 426 ms p50 to 0.7 ms p50, 607x
  faster**. Index time is comparable (~35s for 82k chunks). See
  ``benchmarks/results/bm25_compare__zalo_full.json``.
- **No pickle on the wire.** bm25s ships pure Python + scipy.sparse;
  no native binaries, no pickled artifacts. Passes CLAUDE.md
  principle 11.
- **Standard Okapi formula.** k1 = 1.5, b = 0.75 (Robertson & Zaragoza,
  "The Probabilistic Relevance Framework", FnTIR 2009). Configurable
  on construction. ``method="lucene"`` matches the IDF and tf-norm
  conventions everyone else uses.
- **Lowercased terms.** We lowercase tokens before indexing — VN
  capitalization isn't semantically meaningful for retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from nom.retrieve.base import Hit

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["BM25Retriever"]


@dataclass
class BM25Retriever:
    """In-memory Okapi BM25 retriever for Vietnamese text.

    Construct via :meth:`fit` (factory) — direct construction also works
    if you want to feed precomputed structures.

    Args:
        documents: original document strings (kept for ``Hit.text``).
        tokenized: per-document token lists (lowercased).
        k1: BM25 term-frequency saturation. Default 1.5.
        b: BM25 length-normalization. Default 0.75.

    Example:
        >>> r = BM25Retriever.fit([
        ...     "Hợp đồng số HD-001 ngày 14/3/2025",
        ...     "Công văn số 02 ban hành ngày 1/4/2025",
        ... ])
        >>> hits = r.search("hợp đồng", top_k=2)
        >>> hits[0].idx
        0
    """

    documents: list[str]
    tokenized: list[list[str]]
    k1: float = 1.5
    b: float = 0.75
    name: str = field(default="bm25", init=False)
    _index: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        # bm25s has a small footprint and lazy-imports cleanly. Build the
        # sparse index once at construction so subsequent .search /
        # .score calls are pure lookups.
        try:
            import bm25s
        except ImportError as exc:  # pragma: no cover - exercised in test
            raise ImportError(
                "BM25Retriever requires bm25s. Install with: pip install nom-vn"
            ) from exc

        self._index = bm25s.BM25(method="lucene", k1=self.k1, b=self.b)
        self._index.index(self.tokenized, show_progress=False)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def fit(
        cls,
        documents: list[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> BM25Retriever:
        """Build a BM25 index from a list of strings.

        Tokenizes each document via ``nom.text.word_tokenize``, lowercases,
        builds a sparse term-document matrix.

        Args:
            documents: list of document/chunk strings.
            k1: term-frequency saturation parameter (default 1.5).
            b: length-normalization parameter (default 0.75).

        Returns:
            A ready-to-query :class:`BM25Retriever`.
        """
        if not documents:
            raise ValueError("BM25Retriever.fit requires at least one document")

        from nom.text import word_tokenize

        tokenized: list[list[str]] = []
        for doc in documents:
            toks = word_tokenize(doc)
            assert isinstance(toks, list)  # fmt='list' default
            tokenized.append([t.lower() for t in toks if t.strip()])

        return cls(
            documents=documents,
            tokenized=tokenized,
            k1=k1,
            b=b,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def _query_tokens(self, query: str) -> list[str]:
        """Tokenize + lowercase a query string."""
        from nom.text import word_tokenize

        toks = word_tokenize(query)
        if not isinstance(toks, list):
            toks = list(toks)
        return [t.lower() for t in toks if t.strip()]

    def score(self, query: str) -> NDArray[np.floating[Any]]:
        """Return BM25 scores for every document in the corpus.

        Useful when you need full score arrays (e.g. for hybrid fusion
        or analysis). For top-k queries prefer :meth:`search`.
        """
        q_terms = self._query_tokens(query)
        if not q_terms:
            return np.zeros(len(self.documents), dtype="float32")
        # bm25s returns float64; cast to float32 for downstream parity.
        scores: NDArray[np.floating[Any]] = self._index.get_scores(q_terms)
        return scores.astype("float32", copy=False)

    def search(self, query: str, *, top_k: int = 10) -> list[Hit]:
        """Return up to ``top_k`` highest-scoring docs for ``query``.

        Out-of-vocabulary queries (no token matches the index) → empty
        list. Zero-score results are filtered too — surfacing a document
        with literally no overlap is rarely what callers want.
        """
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        q_terms = self._query_tokens(query)
        if not q_terms:
            return []

        # bm25s.retrieve takes a list-of-queries; we pass one.
        n_docs = len(self.documents)
        k = min(top_k, n_docs)
        results, scores = self._index.retrieve([q_terms], k=k, show_progress=False)
        idxs = results[0].tolist()
        s = scores[0].tolist()
        return [
            Hit(idx=int(i), score=float(sc), text=self.documents[i])
            for i, sc in zip(idxs, s, strict=True)
            if sc > 0
        ]
