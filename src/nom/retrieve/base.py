"""Shared types for :mod:`nom.retrieve` — :class:`Hit` and the Retriever Protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

__all__ = ["Hit", "Retriever"]


@dataclass(frozen=True, slots=True)
class Hit:
    """A single retrieval result.

    Attributes:
        idx: 0-based position in the original corpus.
        score: retriever-specific score. Higher = more relevant.
            BM25 produces unbounded positive scores; cosine is in [-1, 1]
            after L2-normalization. Comparing scores across retrievers is
            unsafe — that's what :func:`nom.retrieve.hybrid_score` is for.
        text: optional payload; the matching document/chunk text. None
            when retrievers return only indices to keep responses small.
    """

    idx: int
    score: float
    text: str | None = None


class Retriever(Protocol):
    """Protocol satisfied by all retriever implementations.

    The minimal contract: build an index from a corpus (or accept
    pre-computed structures), then return ranked :class:`Hit` lists for
    queries. Any concrete class with these signatures works downstream.
    """

    name: str

    def search(self, query: Any, *, top_k: int = 10) -> list[Hit]:
        """Return up to ``top_k`` ``Hit`` objects, sorted by descending score.

        Note ``query`` is intentionally untyped at the Protocol level —
        BM25 wants a string, dense wants a vector. Concrete classes pin
        the type.
        """
        ...
