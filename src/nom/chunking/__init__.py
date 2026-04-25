"""Vietnamese-aware document chunking.

Pure Python — no third-party dependencies, no model files, no network.

The headline function is :func:`smart_chunk`, which takes a string and
splits it into bounded-size pieces respecting Vietnamese sentence and
paragraph boundaries (via :mod:`nom.text`). Each output :class:`Chunk`
carries its character offsets in the source so callers can map back.

For longer-form documents (RAG ingestion), use ``boundary="sentence"``
with ``max_tokens=512`` and ``overlap=64``. For preserving structure
(legal/contract analysis), use ``boundary="paragraph"``. For pathological
inputs (long unbroken text), the algorithm falls back to character-window
chunking with a logged warning attached to the chunk metadata.
"""

from nom.chunking.smart import (
    BoundaryMode,
    Chunk,
    paragraph_chunk,
    sentence_chunk,
    smart_chunk,
)

__all__ = [
    "BoundaryMode",
    "Chunk",
    "paragraph_chunk",
    "sentence_chunk",
    "smart_chunk",
]
