"""Test doubles for ``nom.embeddings.Embedder`` and ``nom.llm.LLM``.

Single source of truth — anywhere in the suite that needs a mock LLM
or embedder imports from here. This avoids the drift we hit when the
fakes were duplicated across `test_chat.py`, `test_multi_space.py`,
and `test_rag.py` (and the bench harness).

The fakes are deliberately deterministic + cheap:
- :class:`FakeEmbedder` hashes text into a small float32 vector.
- :class:`CountingEmbedder` adds call counters for cache-hit assertions.
- :class:`FakeLLM` records every prompt and returns a canned response.
"""

from __future__ import annotations

from typing import Any

import numpy as np


class FakeLLM:
    """Records call history; returns a configurable canned answer."""

    name = "fake-llm"

    def __init__(self, response: str = "Mock answer with [1] citation.") -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        self.calls.append({"prompt": prompt, "schema": schema, "max_tokens": max_tokens})
        return self.response


class FakeEmbedder:
    """Deterministic 16-dim embedder for tests. Hash-seeds an L2-normalized vector."""

    name = "fake-embedder"
    dim = 16

    def embed(self, text: str) -> np.ndarray:
        h = abs(hash(text)) % (2**32)
        rng = np.random.default_rng(h)
        v = rng.standard_normal(self.dim, dtype="float32")
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def embed_batch(self, texts: list[str], *, batch_size: int = 32) -> np.ndarray:
        del batch_size
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")
        return np.stack([self.embed(t) for t in texts])


class CountingEmbedder(FakeEmbedder):
    """Wraps :class:`FakeEmbedder` to count calls.

    Used in cache-hit / re-embedding tests where we want to assert that
    a re-opened ``SqliteStore`` doesn't pay the embed cost again.
    """

    def __init__(self) -> None:
        self.batch_calls = 0
        self.single_calls = 0

    def embed(self, text: str) -> np.ndarray:
        self.single_calls += 1
        return super().embed(text)

    def embed_batch(self, texts: list[str], *, batch_size: int = 32) -> np.ndarray:
        self.batch_calls += 1
        return super().embed_batch(texts, batch_size=batch_size)
