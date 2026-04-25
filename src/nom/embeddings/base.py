"""The :class:`Embedder` Protocol.

Any class with these attributes/methods qualifies — no inheritance from
us required. This is the one place the rest of the toolkit talks to
embedders, so anything that passes type-check here works in
:mod:`nom.retrieve` and :mod:`nom.rag`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

__all__ = ["Embedder"]

# Embedders return float32 arrays by convention. We type the alias once
# here so call-sites read cleanly.
_FloatArray = "NDArray[np.floating[Any]]"


class Embedder(Protocol):
    """Protocol satisfied by all embedder implementations.

    Concrete types (e.g. :class:`VietnameseEmbedder`) provide the
    attributes lazily — the protocol just guarantees they exist after
    a successful ``embed`` or ``embed_batch`` call.

    Attributes:
        name: a short, stable identifier for the embedder (often the
            HuggingFace model id). Used in logs, manifests, cache keys.
        dim: vector dimension. ``None`` until the model has loaded —
            in practice, accessing it triggers the lazy load.

    Methods:
        embed(text): single-string embedding. Returns a 1-D numpy array
            of length ``dim``.
        embed_batch(texts, *, batch_size): batch embedding. Returns a
            2-D numpy array of shape ``(len(texts), dim)``.

    Both methods MUST return L2-normalized vectors so cosine similarity
    reduces to a dot product (what every retrieve/rerank codepath assumes).
    """

    name: str
    dim: int

    def embed(self, text: str) -> NDArray[np.floating[Any]]: ...

    def embed_batch(
        self, texts: list[str], *, batch_size: int = 32
    ) -> NDArray[np.floating[Any]]: ...
