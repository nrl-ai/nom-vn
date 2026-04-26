"""bkai-foundation-models/vietnamese-bi-encoder embedder.

A second VN embedder option that **dramatically beats the BGE-base
fine-tunes on Vietnamese retrieval tasks** (the asymmetric
question-document setup the RAG pipeline actually does).

Measured 2026-04-26 on Zalo Legal QA (5,061 docs, 80 questions):

    Model                                                       R@1     R@10    MRR@10
    dangvantuan/vietnamese-embedding (current default)         35.00 %  67.50 %  0.4449
    bkai-foundation-models/vietnamese-bi-encoder (this class)  76.25 %  98.75 %  0.8604

The +41.25 pp R@1 gap is not a tuning fluke — it's an architectural
mismatch. ``dangvantuan/vietnamese-embedding`` was fine-tuned on STS
(symmetric similarity), not on retrieval triplets. ``bkai`` was trained
with ``MultipleNegativesRankingLoss`` on Q→Doc pairs from MS MARCO +
SQuAD v2 + Zalo Legal — directly the task we run.

The catch: bkai requires **word-segmented input** (multi-syllable VN
words joined with underscores: "đường thủy" → "đường_thủy"). This class
does the segmentation automatically via ``underthesea`` (Apache 2.0).

Install:

    pip install nom-vn[embeddings,nlp]

Both extras are required: ``[embeddings]`` for sentence-transformers,
``[nlp]`` for underthesea.

Example::

    from nom.embeddings import BKaiEmbedder
    e = BKaiEmbedder(device="cuda")
    docs = e.embed_batch(["Hợp đồng số 02 được lập...", "..."])
    docs.shape  # (2, 768)

We do NOT switch the default in ``nom.rag``/``nom.retrieve`` to bkai in
v0.2.x because that would invalidate every existing user's persisted
embedding cache. The 0.3.x major release will flip the default; for now
opt-in keeps cache compatibility.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

__all__ = ["BKaiEmbedder"]


_INSTALL_HINT = (
    "BKaiEmbedder requires sentence-transformers + underthesea. "
    "Install with: pip install 'nom-vn[embeddings,nlp]'"
)


class BKaiEmbedder:
    """VN-specialised retrieval embedder. PhoBERT-base-v2, 100 M params, 768-dim.

    Args:
        model_name: HF id. Default
            ``"bkai-foundation-models/vietnamese-bi-encoder"`` — the
            measured 2026-04-26 winner on Zalo Legal QA at this size class.
        device: ``"cpu"`` (default), ``"cuda"``, or ``"mps"``.
        cache_folder: optional HuggingFace cache override.
        max_seq_length: cap input sequence length. Default 256 (matches the
            model's training cap; raising past 256 hits position-embedding
            overflow).

    The constructor is cheap. Model weights and the underthesea word
    segmenter both load lazily on first ``embed`` / ``embed_batch``.

    Example:
        >>> from nom.embeddings import BKaiEmbedder
        >>> e = BKaiEmbedder()
        >>> v = e.embed("Hợp đồng số 02")
        >>> v.shape
        (768,)
    """

    DEFAULT_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"

    def __init__(
        self,
        model_name: str | None = None,
        *,
        device: str = "cpu",
        cache_folder: str | None = None,
        max_seq_length: int = 256,
    ) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device
        self.cache_folder = cache_folder
        self.max_seq_length = max_seq_length
        self._model: Any | None = None
        self._dim: int | None = None

    @property
    def name(self) -> str:
        return self.model_name

    @property
    def dim(self) -> int:
        self._ensure_loaded()
        assert self._dim is not None
        return self._dim

    def embed(self, text: str) -> NDArray[np.floating[Any]]:
        self._ensure_loaded()
        assert self._model is not None
        segmented = _segment(text)
        return self._model.encode(  # type: ignore[no-any-return,unused-ignore]
            segmented,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def embed_batch(
        self,
        texts: list[str],
        *,
        batch_size: int = 32,
    ) -> NDArray[np.floating[Any]]:
        self._ensure_loaded()
        assert self._model is not None
        if not texts:
            import numpy as np

            return np.zeros((0, self.dim), dtype="float32")
        segmented = [_segment(t) for t in texts]
        return self._model.encode(  # type: ignore[no-any-return,unused-ignore]
            segmented,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise ImportError(_INSTALL_HINT) from exc
        try:
            import underthesea  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(_INSTALL_HINT) from exc

        self._model = SentenceTransformer(
            self.model_name,
            device=self.device,
            cache_folder=self.cache_folder,
        )
        # `get_sentence_embedding_dimension` is renamed to
        # `get_embedding_dimension` in sentence-transformers >=3.x; keep
        # both for forward + backward compat.
        if hasattr(self._model, "get_embedding_dimension"):
            self._dim = self._model.get_embedding_dimension()
        else:
            self._dim = self._model.get_sentence_embedding_dimension()
        with contextlib.suppress(Exception):
            self._model.max_seq_length = self.max_seq_length
            tok = getattr(self._model, "tokenizer", None)
            if tok is not None:
                tok.model_max_length = self.max_seq_length


def _segment(text: str) -> str:
    """Word-segment VN text for bkai input format.

    bkai expects multi-syllable Vietnamese words joined with underscores:
    "đường thủy nội địa" → "đường_thủy nội_địa". This function calls
    underthesea.word_tokenize and applies the underscore convention.
    """
    import underthesea

    tokens = underthesea.word_tokenize(text)
    return " ".join(t.replace(" ", "_") for t in tokens)
