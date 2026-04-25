"""LLM adapter base + provider stubs.

These are typed signatures for v0.1. They raise NotImplementedError today.
The shape is stable — code written against this preview API will continue
to work with the v0.1 implementation.
"""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["LLM", "Anthropic", "Ollama", "OpenAI"]


class LLM(Protocol):
    """Adapter protocol for any LLM backend.

    A minimal interface — providers may add capability methods later
    (streaming, tool-use, vision). v0.1 ships ``complete`` as the floor.
    """

    def complete(self, prompt: str, *, max_tokens: int = 2048) -> str:
        """Send a prompt, return the model's text response."""
        ...


class _Stub:
    """Shared placeholder behavior for v0.0.1 stubs."""

    def __init__(self, **kwargs: Any) -> None:
        self.config = kwargs

    def complete(self, prompt: str, *, max_tokens: int = 2048) -> str:
        cls = type(self).__name__
        raise NotImplementedError(
            f"nom.llm.{cls} is part of v0.1 (planned). "
            f"Track release: https://nrl.ai/nom · star github.com/nrl-ai/nom"
        )


class Ollama(_Stub):
    """Local-inference adapter (Ollama)."""


class OpenAI(_Stub):
    """OpenAI cloud adapter (gpt-4o, gpt-4-turbo, etc.)."""


class Anthropic(_Stub):
    """Anthropic cloud adapter (claude-sonnet, claude-opus, etc.)."""
