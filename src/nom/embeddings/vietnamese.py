"""Vietnamese embedder backed by ``sentence-transformers``.

Design notes:

- **Lazy load.** ``__init__`` is dep-free and side-effect-free. The
  model only loads on the first ``embed`` / ``embed_batch`` / ``dim``
  access. This makes construction cheap in tests and lets users build
  configurations without touching disk.
- **Always normalize.** All output vectors are L2-normalized so cosine
  similarity reduces to a dot product. The :mod:`nom.retrieve` and
  :mod:`nom.rag` codepaths assume this.
- **CPU default.** Defaults to ``device="cpu"`` so the toolkit runs on
  any laptop. Users with GPUs pass ``device="cuda"`` (or ``"mps"`` on
  Apple Silicon) for ~10x single-call speedup.
- **No bundled weights.** We pull from HuggingFace at first use; the
  user's HF cache (default ``~/.cache/huggingface``) does the heavy
  lifting. Weights are ``safetensors`` format — deterministic, no
  arbitrary code on load (passes CLAUDE.md principle 11).

OSS prior art:

- **sentence-transformers** (Apache 2.0) — the de-facto Python interface
  for sentence embeddings. We wrap it; we don't reimplement it. The lib
  itself is a thin layer over HuggingFace transformers + a pooling head.
- **HuggingFace ``hub``** — model loading + safetensors handling. Comes
  in as a transitive dep of sentence-transformers.

Default model rationale: ``dangvantuan/vietnamese-embedding`` is a
fine-tune of BGE-base (multilingual) on Vietnamese parallel data with a
reported STS Pearson of 84.87 — the strongest public number at the
~440 MB / 768-dim class. See: https://huggingface.co/dangvantuan/vietnamese-embedding
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

__all__ = ["VietnameseEmbedder"]


_INSTALL_HINT = (
    "VietnameseEmbedder requires sentence-transformers. "
    "Install with: pip install nom-vn[embeddings]"
)


class VietnameseEmbedder:
    """Embedder for Vietnamese text, default model = BGE-base VN fine-tune.

    Construction is cheap (no disk/network). The model loads on first
    use via :meth:`_ensure_loaded`.

    Args:
        model_name: HuggingFace model id. Defaults to
            ``"dangvantuan/vietnamese-embedding"`` — the recommended
            sweet-spot for VN (768-dim, ~440 MB, Apache 2.0).
        device: passed to sentence-transformers. ``"cpu"`` (default),
            ``"cuda"`` for NVIDIA GPU, ``"mps"`` for Apple Silicon.
        cache_folder: optional HuggingFace cache override. Defaults to
            ``~/.cache/huggingface``.

    Example:
        >>> from nom.embeddings import VietnameseEmbedder
        >>> e = VietnameseEmbedder()                              # cheap
        >>> v = e.embed("Hợp đồng số 02")                         # triggers load
        >>> v.shape
        (768,)
    """

    DEFAULT_MODEL = "dangvantuan/vietnamese-embedding"

    def __init__(
        self,
        model_name: str | None = None,
        *,
        device: str = "cpu",
        cache_folder: str | None = None,
    ) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device
        self.cache_folder = cache_folder
        self._model: Any | None = None  # lazy
        self._dim: int | None = None  # set after load

    @property
    def name(self) -> str:
        """The model id — stable across runs even before load."""
        return self.model_name

    @property
    def dim(self) -> int:
        """Embedding dimension. Triggers model load on first access."""
        self._ensure_loaded()
        assert self._dim is not None
        return self._dim

    def embed(self, text: str) -> NDArray[np.floating[Any]]:
        """Embed a single string, returning an L2-normalized 1-D vector.

        Args:
            text: input. Empty string → zero vector (deterministic).

        Returns:
            1-D numpy array of length :attr:`dim`.
        """
        self._ensure_loaded()
        assert self._model is not None
        # encode returns shape (dim,) for a single str when convert_to_numpy=True
        return self._model.encode(  # type: ignore[no-any-return,unused-ignore]
            text,
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
        """Embed a list of strings, returning an L2-normalized 2-D array.

        Args:
            texts: list of input strings. Empty list → empty array of
                shape ``(0, dim)``.
            batch_size: how many texts to encode per forward pass.
                Default 32 — balanced for laptops; bump to 64-128 on
                GPU for higher throughput.

        Returns:
            2-D numpy array of shape ``(len(texts), dim)``.
        """
        self._ensure_loaded()
        assert self._model is not None
        if not texts:
            import numpy as np

            return np.zeros((0, self.dim), dtype="float32")
        return self._model.encode(  # type: ignore[no-any-return,unused-ignore]
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def _ensure_loaded(self) -> None:
        """Load the underlying SentenceTransformer model if not yet loaded."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised in test
            raise ImportError(_INSTALL_HINT) from exc

        self._model = SentenceTransformer(
            self.model_name,
            device=self.device,
            cache_folder=self.cache_folder,
        )
        self._dim = self._model.get_sentence_embedding_dimension()
        # Hard-cap sequence length to the *real* size of the model's
        # position-embedding table, not the model card's `max_seq_length`.
        #
        # We've seen ``dangvantuan/vietnamese-embedding`` advertise
        # max_seq_length=512 while the actual position-embeddings table
        # is 258 entries — a misconfiguration on the upstream model card
        # that makes any input >~256 subwords trigger an IndexError /
        # CUDA assert in F.embedding (the "padding_idx + cumsum"
        # XLM-RoBERTa quirk magnifies this off-by-one). We've also seen
        # AITeamVN/Vietnamese_Embedding (BGE-M3) advertise 8192 while
        # the table is 8194. Trust the table, not the card.
        actual_pos = self._actual_position_table_size()
        advertised = int(getattr(self._model, "max_seq_length", 512) or 512)
        # Leave 2-token headroom for [CLS]/[SEP] + the +padding_idx
        # offset XLM-RoBERTa adds.
        cap = max(8, min(advertised, actual_pos - 4))
        self._model.max_seq_length = cap
        tok = getattr(self._model, "tokenizer", None)
        if tok is not None:
            with contextlib.suppress(Exception):
                tok.model_max_length = cap

    def _actual_position_table_size(self) -> int:
        """Return the number of rows in the position-embeddings table.

        Walks the SentenceTransformer module to find the underlying
        transformer's positional embeddings. Returns a high default if
        we can't introspect (some encoder types don't have absolute
        position embeddings — they use rotary or relative — and don't
        have this overflow class of bug).
        """
        try:
            assert self._model is not None  # narrowed by _ensure_loaded callers
            mod = self._model._first_module()
            auto = getattr(mod, "auto_model", None)
            if auto is None:
                return 100_000
            emb = getattr(auto, "embeddings", None)
            if emb is None:
                return 100_000
            pos = getattr(emb, "position_embeddings", None)
            if pos is None:
                return 100_000
            return int(pos.num_embeddings)
        except Exception:
            return 100_000

    def __repr__(self) -> str:
        loaded = "loaded" if self._model is not None else "lazy"
        return f"VietnameseEmbedder(model={self.model_name!r}, device={self.device!r}, {loaded})"
