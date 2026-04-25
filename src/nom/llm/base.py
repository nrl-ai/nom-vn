"""LLM adapter base + provider stubs.

The :class:`LLM` Protocol defines the minimal interface. Real adapters
live in their own modules:

- :mod:`nom.llm.ollama` — local Ollama server (httpx, real)
- ``nom.llm.openai`` — OpenAI cloud (planned for v0.1.1)
- ``nom.llm.anthropic`` — Anthropic cloud (planned for v0.1.1)

Cloud adapters are stubs in this file until their full implementations
land. Code calling ``Ollama(...).complete(...)`` works today.
"""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["LLM", "Anthropic", "OpenAI"]


class LLM(Protocol):
    """Adapter protocol for any LLM backend.

    Minimal contract: a stateless ``complete`` method that takes a prompt
    and an optional JSON schema and returns the model's text response.

    Adapters may add capability methods later (streaming, vision, tool use)
    but ``complete`` is the floor — Extract only calls this one.
    """

    name: str

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt, return the model's text response."""
        ...


class _CloudStub:
    """Placeholder for cloud adapters until real impls land in v0.1.1."""

    name = "stub"

    def __init__(self, **kwargs: Any) -> None:
        self.config = kwargs

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        cls = type(self).__name__
        raise NotImplementedError(
            f"nom.llm.{cls} ships in v0.1.1 (planned). "
            f"For local inference today, use nom.llm.Ollama. "
            f"Track release: https://github.com/nrl-ai/nom"
        )


class OpenAI(_CloudStub):
    """OpenAI cloud adapter (gpt-4o, gpt-4-turbo, etc.). Planned v0.1.1."""

    name = "openai"


class Anthropic(_CloudStub):
    """Anthropic cloud adapter (claude-sonnet, claude-opus, etc.). Planned v0.1.1."""

    name = "anthropic"
