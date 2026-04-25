"""Vietnamese-aware text embeddings.

Provides:

- :class:`Embedder` — Protocol that any embedder satisfies (built-in or
  user-supplied).
- :class:`VietnameseEmbedder` — wraps a sentence-transformers model
  fine-tuned for Vietnamese. Lazy-loads on first use; ``__init__`` is
  free of network and disk I/O.

Default model: ``dangvantuan/vietnamese-embedding`` — a BGE-base
fine-tune that posts the highest public Vietnamese STS Pearson at its
size class (84.87, 768-dim, ~440 MB on disk, Apache 2.0, safetensors).
Swap to ``paraphrase-multilingual-MiniLM-L12-v2`` (~120 MB, 384-dim) for
edge/CPU; swap to ``AITeamVN/Vietnamese_Embedding`` (BGE-M3 ft, ~2 GB,
1024-dim) for highest reported VN retrieval quality on VN-MTEB.

Install: ``pip install nom-vn[embeddings]`` (adds ``sentence-transformers``).
"""

from nom.embeddings.base import Embedder
from nom.embeddings.vietnamese import VietnameseEmbedder

__all__ = ["Embedder", "VietnameseEmbedder"]
