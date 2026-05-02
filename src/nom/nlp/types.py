"""Shared value types for ``nom.nlp``."""

from __future__ import annotations

__all__ = ["NLPError"]


class NLPError(Exception):
    """An NLP module failed in a way the caller can recover from.

    Use over ``RuntimeError`` so consumers can ``except NLPError`` and
    fall back to a simpler primitive (e.g. drop NER on input over a
    length cap, retry with a smaller model, etc.).
    """
