"""Dense (cosine) retrieval over a precomputed embeddings matrix.

Implementation notes:

- **Assumes L2-normalized rows.** Cosine similarity reduces to dot
  product, so the runtime is one matrix-vector multiply. This is the
  contract :class:`nom.embeddings.Embedder` enforces.
- **Pure numpy.** No faiss, no scipy. ``argpartition`` for top_k beats
  a full sort for typical k in the dozens-to-hundreds range.
- **In-process only.** Holds the entire embeddings matrix in RAM.
  For ~100k chunks at 768-dim float32 that's ~300 MB — fine. Beyond
  that, switch to :mod:`nom.index` (planned v0.1).
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
        embeddings: ``(N, D)`` numpy array, **L2-normalized rows**.
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
                L2-normalized (callers are responsible).
        """
        if query_vector.ndim != 1:
            raise ValueError(f"query_vector must be 1-D, got shape {query_vector.shape}")
        if query_vector.shape[0] != self.dim:
            raise ValueError(
                f"query_vector dim {query_vector.shape[0]} != embeddings dim {self.dim}"
            )
        # (N, D) @ (D,) → (N,). Float32 throughout for memory.
        return self.embeddings @ query_vector.astype(self.embeddings.dtype, copy=False)

    def search(self, query_vector: NDArray[np.floating], *, top_k: int = 10) -> list[Hit]:
        """Return up to ``top_k`` nearest neighbors by cosine similarity."""
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        scores = self.score(query_vector)
        n = len(scores)
        if n == 0:
            return []
        k = min(top_k, n)
        # argpartition for top-k unsorted, then sort just those
        partition = np.argpartition(-scores, k - 1)[:k]
        ordered = partition[np.argsort(-scores[partition])]
        return [
            Hit(
                idx=int(i),
                score=float(scores[i]),
                text=(self.documents[i] if self.documents is not None else None),
            )
            for i in ordered
        ]
