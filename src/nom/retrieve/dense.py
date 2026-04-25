"""Dense (cosine) retrieval over a precomputed embeddings matrix.

Implementation notes:

- **Assumes L2-normalized rows.** Cosine similarity reduces to dot
  product, so the runtime is one matrix-vector multiply. This is the
  contract :class:`nom.embeddings.Embedder` enforces.
- **Pure numpy.** No faiss, no scipy. The hot path is a single matmul
  plus an argpartition for top-k. We pre-validate dtypes so the matmul
  doesn't pay the ``astype`` dance per call.
- **In-process only.** Holds the entire embeddings matrix in RAM.
  For ~100k chunks at 768-dim float32 that's ~300 MB — fine. Beyond
  that, switch to :mod:`nom.index` (planned v0.1).

Performance tuning (v0.0.6 vs v0.0.5):

- v0.0.5 baseline: 8.98 ms / query (1k docs at 768-dim, p50). Hot path:
  ``(N, D) @ (D,)`` + ``argpartition(-scores, k-1)`` + ``argsort`` +
  list comp.
- v0.0.6 changes (this file):
  1. Drop the per-call ``query_vector.astype(...)`` — instead validate
     dtype at construction so the matmul gets clean inputs every call.
  2. Use ``argpartition(scores, -k)[-k:]`` (find k largest directly)
     instead of ``argpartition(-scores, k-1)[:k]`` — avoids the
     negation copy of the full N-element score array.
  3. Skip ``argsort`` overhead when ``top_k == 1`` — common case.
  4. Localize ``self.embeddings`` and ``self.documents`` references
     into stack vars in the hot loop.
- Re-bench: ``benchmarks/perf/bench_retrieve.py``; baseline JSON updated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from nom.retrieve.base import Hit

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["DenseRetriever"]


@dataclass
class DenseRetriever:
    """Dense retriever over a precomputed embeddings matrix.

    Args:
        embeddings: ``(N, D)`` numpy array, **L2-normalized rows**. Will
            be coerced to ``float32`` and made C-contiguous at
            construction so the matmul gets clean inputs every call.
        documents: optional list of document strings (length N) for
            populating ``Hit.text``. When None, hits return text=None.

    Example:
        >>> # vecs comes from VietnameseEmbedder.embed_batch(documents)
        >>> r = DenseRetriever(vecs, documents=docs)
        >>> q = embedder.embed("hợp đồng")
        >>> hits = r.search(q, top_k=5)
    """

    embeddings: NDArray[np.floating]
    documents: list[str] | None = None
    name: str = field(default="dense", init=False)

    def __post_init__(self) -> None:
        if self.embeddings.ndim != 2:
            raise ValueError(f"embeddings must be 2-D (N, D), got shape {self.embeddings.shape}")
        if self.documents is not None and len(self.documents) != self.embeddings.shape[0]:
            raise ValueError(
                f"documents has length {len(self.documents)}, "
                f"embeddings has {self.embeddings.shape[0]} rows"
            )
        # Ensure float32 C-contiguous storage for fast matmul. ascontiguousarray
        # is a no-op when input is already correct (zero copy).
        if self.embeddings.dtype != np.float32:
            self.embeddings = self.embeddings.astype(np.float32, copy=False)
        if not self.embeddings.flags["C_CONTIGUOUS"]:
            self.embeddings = np.ascontiguousarray(self.embeddings)

    @property
    def n_docs(self) -> int:
        return int(self.embeddings.shape[0])

    @property
    def dim(self) -> int:
        return int(self.embeddings.shape[1])

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def score(self, query_vector: NDArray[np.floating]) -> NDArray[np.floating]:
        """Return cosine similarity (= dot product, given normalized inputs)
        between ``query_vector`` and every doc embedding.

        Args:
            query_vector: 1-D numpy array of shape ``(dim,)``. Should be
                L2-normalized (callers are responsible). Will be coerced
                to ``float32`` if needed.
        """
        if query_vector.ndim != 1:
            raise ValueError(f"query_vector must be 1-D, got shape {query_vector.shape}")
        if query_vector.shape[0] != self.dim:
            raise ValueError(
                f"query_vector dim {query_vector.shape[0]} != embeddings dim {self.dim}"
            )
        # Coerce dtype only when needed; the embeddings matrix is already
        # float32-C-contiguous from __post_init__.
        q = (
            query_vector
            if query_vector.dtype == np.float32
            else query_vector.astype(np.float32, copy=False)
        )
        # (N, D) @ (D,) → (N,). One BLAS call.
        return self.embeddings @ q

    def search(self, query_vector: NDArray[np.floating], *, top_k: int = 10) -> list[Hit]:
        """Return up to ``top_k`` nearest neighbors by cosine similarity.

        Hot-path notes (v0.0.6 retune):
        - ``argpartition(scores, -k)[-k:]`` finds the k largest **without**
          negating the full score array (avoids an N-element copy).
        - ``argsort`` runs over only the k partitioned indices.
        - Document/score lookups are localized in the comprehension.
        """
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")

        scores = self.score(query_vector)
        n = scores.shape[0]
        if n == 0:
            return []

        k = min(top_k, n)

        if k == n:
            # Asking for everything — full sort by descending score
            ordered = np.argsort(-scores)
        elif k == 1:
            # Common case: single best — argmax is fastest
            ordered = np.array([int(np.argmax(scores))], dtype=np.intp)
        else:
            # k largest, then sort just those k (descending)
            partition = np.argpartition(scores, -k)[-k:]
            ordered = partition[np.argsort(-scores[partition])]

        # Localize attribute lookups outside the hot loop.
        docs = self.documents
        scores_ndarray = scores  # already a local in our scope but be explicit

        if docs is None:
            return [Hit(idx=int(i), score=float(scores_ndarray[i])) for i in ordered]
        return [Hit(idx=int(i), score=float(scores_ndarray[i]), text=docs[i]) for i in ordered]
