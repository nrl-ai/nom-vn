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

SOTA notes (April 2026): VN-MTEB (arXiv 2507.21500) Table 3 ranks 41
datasets across 6 tasks. The actual top of that table is
``intfloat/multilingual-e5-large-instruct`` at **67.99 overall**, with
``intfloat/e5-mistral-7b-instruct`` (67.67) and
``Alibaba-NLP/gte-Qwen2-7B-instruct`` (65.84) above ``BAAI/bge-m3``
(roughly 4th, 64.90). For the **legal-domain retrieval** axis
specifically, ``AITeamVN/Vietnamese_Embedding`` (BGE-M3 finetune)
reports +27.9% Acc@1 over base BGE-M3 on Zalo Legal — verified on the
HF model card with held-out 20% split. See ``docs/sota_vn_2026q2.md``
for the full citations and tier picks.

Install: ``pip install nom-vn[embeddings]`` (adds ``sentence-transformers``).
"""

from nom.embeddings.aiteamvn import AITeamVNEmbedder
from nom.embeddings.base import Embedder
from nom.embeddings.bkai import BKaiEmbedder
from nom.embeddings.vietnamese import VietnameseEmbedder

__all__ = ["AITeamVNEmbedder", "BKaiEmbedder", "Embedder", "VietnameseEmbedder"]
