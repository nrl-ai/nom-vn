"""``AITeamVN/Vietnamese_Embedding`` — heavier, higher-quality VN embedder.

A drop-in replacement for :class:`VietnameseEmbedder` that loads
``AITeamVN/Vietnamese_Embedding`` (a fine-tune of BGE-M3 on Vietnamese
data) instead of ``dangvantuan/vietnamese-embedding`` (a fine-tune of
BGE-base).

| | Default (`VietnameseEmbedder`) | This class (`AITeamVNEmbedder`) |
|---|---|---|
| HuggingFace id | ``dangvantuan/vietnamese-embedding`` | ``AITeamVN/Vietnamese_Embedding`` |
| Base model | BGE-base | BGE-M3 |
| Vector dim | 768 | 1024 |
| On-disk weights | ~440 MB | ~2.3 GB |
| Max context | 512 tokens | 2048 tokens |
| License | Apache 2.0, safetensors | Apache 2.0, safetensors |

**Reported quality (verified in the published HF model card on Zalo
Legal QA, held-out 20% split):**

- Acc@1: **0.7274** vs **0.5682** for base BGE-M3 → **+27.9%**
- MRR@10: **0.8181** vs **0.6822** for base BGE-M3

Source: https://huggingface.co/AITeamVN/Vietnamese_Embedding (model card,
fetched April 2026).

The Acc@1 lift over base BGE-M3 is on legal-domain retrieval. The
model is *not* separately ranked in VN-MTEB Table 3 (arXiv 2507.21500);
treat the gain as verified for legal-domain retrieval and unverified
across other VN tasks until measured. Re-bench against your own
corpus via ``benchmarks/rag/bench_rag_vn.py`` before promoting it
your default for non-legal text.

**When to choose this over** :class:`VietnameseEmbedder`:

- You have ≥4 GB of free RAM (or a small GPU) and your corpus is
  legal / formal Vietnamese.
- You're embedding long documents (the 2048 ctx avoids over-chunking
  what a 512-ctx model would split).

**When to stay with** :class:`VietnameseEmbedder`:

- CPU laptop without a GPU (forward pass on CPU is ~5x slower at the
  M3 size class).
- General-domain text where the legal-specific gain doesn't apply.
- Existing ``SqliteStore`` data dirs already indexed at dim 768
  (mixing dims raises ``ValueError`` at index time — that's by
  design, see :class:`nom.chat.SqliteStore`).
"""

from __future__ import annotations

from nom.embeddings.vietnamese import VietnameseEmbedder

__all__ = ["AITeamVNEmbedder"]


class AITeamVNEmbedder(VietnameseEmbedder):
    """BGE-M3 fine-tune for Vietnamese.

    Construction is cheap (no disk/network). Model loads on first
    ``embed`` / ``embed_batch`` / ``dim`` access, same lazy-load
    contract as the parent class.

    Example:
        >>> from nom.embeddings import AITeamVNEmbedder
        >>> e = AITeamVNEmbedder()                           # cheap
        >>> v = e.embed("Hợp đồng số 02")                     # triggers load
        >>> v.shape
        (1024,)
    """

    DEFAULT_MODEL = "AITeamVN/Vietnamese_Embedding"

    def __repr__(self) -> str:
        loaded = "loaded" if self._model is not None else "lazy"
        return f"AITeamVNEmbedder(model={self.model_name!r}, device={self.device!r}, {loaded})"
