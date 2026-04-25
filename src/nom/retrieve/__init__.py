"""In-process retrieval primitives over Vietnamese text.

Three building blocks, each pure-Python + numpy, no third-party deps:

- :class:`BM25Retriever` — Okapi BM25 over Vietnamese-tokenized text
  (``nom.text.word_tokenize`` for compound-word aware indexing).
- :class:`DenseRetriever` — cosine similarity over an already-computed
  embeddings matrix. Assumes L2-normalized rows (what
  :class:`nom.embeddings.VietnameseEmbedder` produces).
- :func:`hybrid_score` — combine the hits from multiple retrievers via
  Reciprocal Rank Fusion (default) or weighted sum.

Designed for **in-process** use: corpora up to ~100k chunks fit in RAM
and answer queries in milliseconds. Beyond that, lift the same
``Retriever`` Protocol into ``nom.index`` (planned v0.1) backed by
ChromaDB / Qdrant / pgvector.

OSS prior art studied:

- **rank-bm25** (Apache 2.0) — the canonical Python BM25. We
  reimplement so we can use ``nom.text.word_tokenize`` for VN compound
  awareness and avoid the dep.
- **bm25s** (MIT, scipy.sparse) — fastest pure-Python BM25. We borrow
  the algorithmic shape (precomputed IDF + per-doc TF) but keep numpy-
  dense storage for now; sparse becomes optional in v0.0.6 if profiling
  shows it matters at larger corpora.
- **Reciprocal Rank Fusion** (Cormack, Clarke, Buettcher; SIGIR 2009)
  — robust parameter-free score combination. Default ``k=60``.
- **faiss** (MIT) — considered for dense retrieval; rejected at the
  in-process tier because it bundles native binaries we'd have to audit
  per principle 11. ``numpy.argpartition`` is fast enough up to 100k
  vectors. Future ``nom.index`` may add it as opt-in for huge indexes.
"""

from nom.retrieve.base import Hit, Retriever
from nom.retrieve.bm25 import BM25Retriever
from nom.retrieve.dense import DenseRetriever
from nom.retrieve.hybrid import FusionMethod, hybrid_score

__all__ = [
    "BM25Retriever",
    "DenseRetriever",
    "FusionMethod",
    "Hit",
    "Retriever",
    "hybrid_score",
]
