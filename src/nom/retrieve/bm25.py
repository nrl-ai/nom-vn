"""Okapi BM25 over Vietnamese-tokenized text.

Implementation notes:

- **VN-aware tokenization.** Documents and queries flow through
  ``nom.text.word_tokenize`` so compound words (``"Hợp đồng"``,
  ``"thành phố Hồ Chí Minh"``) count as single terms — matches the
  way humans index VN docs.
- **Standard Okapi formula.** k1 = 1.5, b = 0.75 are the de-facto
  defaults (Robertson & Zaragoza, "The Probabilistic Relevance
  Framework", FnTIR 2009). Configurable on construction.
- **Numpy storage.** Term-document matrix as an ``object`` array of
  per-doc Counter dicts; IDF + average doc length precomputed at
  ``fit`` time. Enough for ~100k docs; sparse storage becomes opt-in
  in v0.0.6 if benchmarks justify it.
- **Lowercased terms.** We lowercase tokens before indexing — VN
  capitalization isn't semantically meaningful for retrieval.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import log
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
        idf: term → IDF mapping. Computed in :meth:`fit`.
        avg_dl: corpus-mean document length in tokens.
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
    idf: dict[str, float]
    avg_dl: float
    k1: float = 1.5
    b: float = 0.75
    name: str = field(default="bm25", init=False)
    _doc_counters: list[Counter[str]] = field(default_factory=list, init=False, repr=False)
    _doc_lengths: NDArray[np.floating[Any]] = field(
        default_factory=lambda: np.zeros(0, dtype="float32"),
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        # Precompute per-doc Counter and length array for fast scoring.
        self._doc_counters = [Counter(toks) for toks in self.tokenized]
        self._doc_lengths = np.asarray([len(toks) for toks in self.tokenized], dtype="float32")

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
        computes IDF and average document length.

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

        n_docs = len(documents)
        # Document frequency: how many docs contain each term?
        doc_freq: Counter[str] = Counter()
        for toks in tokenized:
            for term in set(toks):
                doc_freq[term] += 1

        # Smoothed IDF (BM25 + 0.5 smoothing). Clamp to 0 to avoid
        # negative IDF for terms in >50% of docs (Robertson recommends
        # +1 in the log to keep it non-negative).
        idf = {term: log((n_docs - df + 0.5) / (df + 0.5) + 1.0) for term, df in doc_freq.items()}
        avg_dl = float(sum(len(t) for t in tokenized)) / n_docs

        return cls(
            documents=documents,
            tokenized=tokenized,
            idf=idf,
            avg_dl=avg_dl,
            k1=k1,
            b=b,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def score(self, query: str) -> NDArray[np.floating[Any]]:
        """Return BM25 scores for every document in the corpus.

        Useful when you need full score arrays (e.g. for hybrid fusion
        or analysis). For top-k queries prefer :meth:`search`.
        """
        from nom.text import word_tokenize

        q_tokens = word_tokenize(query)
        assert isinstance(q_tokens, list)
        q_terms = [t.lower() for t in q_tokens if t.strip()]

        scores = np.zeros(len(self.documents), dtype="float32")
        if not q_terms:
            return scores

        # Vectorized scoring: for each query term, accumulate contribution
        # across all docs.
        for term in q_terms:
            term_idf = self.idf.get(term)
            if term_idf is None:
                continue  # OOV — contributes 0
            # Per-doc tf for this term (zeros where absent)
            tf = np.asarray(
                [c.get(term, 0) for c in self._doc_counters],
                dtype="float32",
            )
            # BM25 term contribution
            denom = tf + self.k1 * (1.0 - self.b + self.b * (self._doc_lengths / self.avg_dl))
            # Avoid divide-by-zero on empty docs (denom can be 0 only if
            # k1*(1-b) == 0 AND tf == 0 AND b*L/avg_dl == 0; protect anyway).
            np.maximum(denom, 1e-12, out=denom)
            scores += term_idf * (tf * (self.k1 + 1.0)) / denom

        return scores

    def search(self, query: str, *, top_k: int = 10) -> list[Hit]:
        """Return up to ``top_k`` highest-scoring docs for ``query``."""
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        scores = self.score(query)
        if not len(scores):
            return []
        # argpartition gives unsorted top_k indices — faster than full sort.
        k = min(top_k, len(scores))
        partition_idx = np.argpartition(-scores, k - 1)[:k]
        # Sort just the top_k by descending score
        ordered = partition_idx[np.argsort(-scores[partition_idx])]
        return [
            Hit(idx=int(i), score=float(scores[i]), text=self.documents[i])
            for i in ordered
            if scores[i] > 0  # don't surface irrelevant docs
        ]
