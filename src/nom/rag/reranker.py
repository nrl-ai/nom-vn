"""Cross-encoder reranker stage for the RAG pipeline.

Bi-encoders (BM25 + dense) are fast but lossy: they score query and
document independently, never seeing both at once. A **cross-encoder**
takes the (query, document) pair as a single input and outputs one
relevance score, capturing token-level interactions a bi-encoder can't.
The cost: O(N) forward passes per query instead of O(1) — feasible only
for the small candidate pool that bi-encoders surface first.

The standard pattern (universal across the 2024-2025 Vietnamese legal
RAG papers we surveyed — see ``research/2026-04-25-zalo-legal-qa/``):

    BM25 + dense  →  top 30 candidates  →  cross-encoder rerank  →  top 8  →  LLM

Quality lift typically reported: +20-28% NDCG@10 over bi-encoder-only
retrieval. Latency: ~30-50 ms on GPU, ~100-150 ms on CPU for 30 pairs
with a 600M-param model. (We do not claim our own numbers until
``benchmarks/rag/`` is wired against a real VN corpus — CLAUDE.md
principle 12.)

Default model: ``BAAI/bge-reranker-v2-m3`` — Apache 2.0, safetensors,
600M params on the BGE-M3 multilingual backbone, no special
preprocessing. Battle-tested in production RAG stacks.

Two strong VN-specific alternatives are documented and one-line
swappable:

- ``namdp-ptit/ViRanker`` (Apache 2.0, BGE-M3 base, best NDCG@3 on
  MMARCO-VI per arXiv:2509.09131). No preprocessing needed.
- ``itdainb/PhoRanker`` (Apache 2.0, 100M params, best NDCG@10 on
  MMARCO-VI). **Requires VnCoreNLP word segmentation** (Java JVM
  dependency) — use only if you've already wired that up; otherwise
  the default or ViRanker is the safer pick.

Install: ``pip install nom-vn[embeddings]`` already pulls
sentence-transformers, which provides ``CrossEncoder``. No new dep.

Example:

    >>> from nom.rag import RAG, CrossEncoderReranker
    >>> from nom.llm import Ollama
    >>> rag = RAG.from_documents(
    ...     ["a.pdf", "b.pdf"],
    ...     llm=Ollama(model="qwen3:8b"),
    ...     reranker=CrossEncoderReranker(),
    ... )
    >>> answer = rag.ask("What's the deadline?", rerank=True)

OSS prior art:

- **sentence-transformers** ``CrossEncoder`` (Apache 2.0) — the de-facto
  Python interface for cross-encoder rerankers. We wrap it; we don't
  reimplement.
- **FlagEmbedding** (MIT) — BAAI's first-party wrapper. We don't take
  a dep on it because sentence-transformers loads the same safetensors
  weights with the same numerics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from nom.retrieve import Hit

__all__ = ["CrossEncoderReranker", "Reranker"]


_INSTALL_HINT = (
    "CrossEncoderReranker requires sentence-transformers. "
    "Install with: pip install nom-vn[embeddings]"
)


@runtime_checkable
class Reranker(Protocol):
    """Protocol satisfied by all rerankers.

    A reranker takes a query and a list of bi-encoder ``Hit`` candidates
    and returns the same hits resorted by a richer relevance signal,
    truncated to ``top_k``. ``Hit.score`` is replaced with the reranker's
    score; ``Hit.idx`` and ``Hit.text`` are preserved so downstream
    citation lookup still works.
    """

    name: str

    def rerank(self, query: str, hits: list[Hit], *, top_k: int) -> list[Hit]:
        """Resort ``hits`` by query relevance, return up to ``top_k``."""
        ...


class CrossEncoderReranker:
    """Cross-encoder reranker via ``sentence_transformers.CrossEncoder``.

    Construction is cheap (no disk/network). The model loads on first
    :meth:`rerank` call.

    Args:
        model_name: HuggingFace model id. Defaults to
            ``"BAAI/bge-reranker-v2-m3"`` — Apache 2.0, safetensors,
            multilingual including Vietnamese.
        device: passed to sentence-transformers. ``"cpu"`` (default),
            ``"cuda"`` for NVIDIA, ``"mps"`` for Apple Silicon.
        max_length: max tokens per (query, doc) pair. Default 512 —
            matches the BGE / ViRanker context size. Lower to 256 if
            using PhoRanker (its position table is 256).
        cache_folder: HuggingFace cache override. ``None`` uses the
            default ``~/.cache/huggingface``.
        use_fp16: load weights in fp16 to halve memory + speed up GPU
            inference. Default True; set False if you see numerical
            instability on your hardware.

    Example:
        >>> r = CrossEncoderReranker()                     # cheap
        >>> # ... later, after BM25/dense retrieval ...
        >>> top_pairs = r.rerank("câu hỏi", hits, top_k=8)  # triggers load
    """

    DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"

    def __init__(
        self,
        model_name: str | None = None,
        *,
        device: str = "cpu",
        max_length: int | None = None,
        cache_folder: str | None = None,
        use_fp16: bool = True,
    ) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device
        # max_length=None → auto-detect from the model's config on load.
        # PhoBERT-base rerankers (PhoRanker) cap at 256; XLM-RoBERTa-large
        # rerankers (bge-reranker-v2-m3, ViRanker) cap at 514. Without auto
        # detect, we'd send 512-cap pairs to PhoRanker and trip the SDPA
        # CUDA assert. Explicit override still wins when caller knows better.
        self.max_length = max_length
        self.cache_folder = cache_folder
        self.use_fp16 = use_fp16
        self._model: Any | None = None  # lazy

    @property
    def name(self) -> str:
        """The model id — stable across runs even before load."""
        return self.model_name

    def rerank(self, query: str, hits: list[Hit], *, top_k: int) -> list[Hit]:
        """Resort ``hits`` by cross-encoder relevance.

        Args:
            query: the user's question (or a HyDE/multi-query expansion
                — anything stringy is fine).
            hits: candidate ``Hit`` objects from the bi-encoder stage.
                Each must have ``text`` populated; pass-through is no-op
                if a hit's text is None or empty.
            top_k: how many top hits to return after reranking.

        Returns:
            A new list of ``Hit`` objects sorted by descending
            cross-encoder score, truncated to ``top_k``. Each hit's
            ``score`` is the cross-encoder logit (raw, not sigmoid).
            Empty input → empty output. ``top_k <= 0`` → empty output.
        """
        if not query.strip():
            raise ValueError("rerank() requires a non-empty query")
        if top_k <= 0 or not hits:
            return []

        # Filter out hits without text — we can't rerank what we can't read.
        scorable = [h for h in hits if h.text]
        if not scorable:
            return []

        self._ensure_loaded()
        assert self._model is not None
        pairs = [(query, h.text or "") for h in scorable]
        scores = self._model.predict(
            pairs,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        from nom.retrieve import Hit as _Hit

        ranked = sorted(
            (
                _Hit(idx=h.idx, score=float(s), text=h.text)
                for h, s in zip(scorable, scores, strict=True)
            ),
            key=lambda h: h.score,
            reverse=True,
        )
        return ranked[:top_k]

    def _ensure_loaded(self) -> None:
        """Load the underlying CrossEncoder if not yet loaded."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - exercised by import-error path
            raise ImportError(_INSTALL_HINT) from exc

        max_length = self.max_length or self._auto_detect_max_length()
        kwargs: dict[str, Any] = {
            "max_length": max_length,
            "device": self.device,
        }
        if self.cache_folder is not None:
            kwargs["cache_folder"] = self.cache_folder

        self._model = CrossEncoder(self.model_name, **kwargs)
        # Cache the resolved value back on the instance so callers can
        # introspect what was actually used.
        self.max_length = max_length

        # fp16 halves memory + ~2x speedup on GPU; on CPU it's a no-op
        # (PyTorch CPU paths run fp32 regardless), so we only attempt
        # the cast when the device is GPU-class.
        if self.use_fp16 and self.device != "cpu":
            inner = getattr(self._model, "model", None)
            if inner is not None and hasattr(inner, "half"):
                inner.half()

    def _auto_detect_max_length(self) -> int:
        """Inspect the model's config.json to find a safe truncation cap.

        PhoBERT-base reports max_position_embeddings=258, real cap 256
        (the +2 is the offset for [CLS]/[SEP] padding ids). XLM-RoBERTa-large
        reports 514, real cap 512. Without this auto-detect, downstream
        callers have to know which family their reranker is and pass
        ``max_length=`` explicitly — easy to forget and the failure mode
        is a CUDA device-side assert deep in the SDPA attention path.
        """
        try:
            from transformers import AutoConfig
        except ImportError:
            return 512  # safe-ish default if transformers isn't around
        try:
            cfg = AutoConfig.from_pretrained(self.model_name)
            advertised = int(getattr(cfg, "max_position_embeddings", 514) or 514)
            # XLM-RoBERTa et al. add +2 for the offset; subtract a small
            # headroom and clamp to 512 to avoid surprises.
            return max(64, min(advertised - 2, 512))
        except (ValueError, OSError, AttributeError):
            return 512

    def __repr__(self) -> str:
        loaded = "loaded" if self._model is not None else "lazy"
        return f"CrossEncoderReranker(model={self.model_name!r}, device={self.device!r}, {loaded})"
