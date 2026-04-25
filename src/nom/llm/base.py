"""LLM adapter Protocol — the single contract every backend implements.

Real adapters live in their own modules so importing :mod:`nom.llm`
stays cheap (no httpx import until you instantiate one):

- :mod:`nom.llm.ollama` — local Ollama server
- :mod:`nom.llm.openai` — OpenAI cloud + any OpenAI-compatible
  endpoint (Azure, DeepSeek, OpenRouter, LiteLLM, vLLM, Together,
  Groq, …) via ``base_url=``
- :mod:`nom.llm.anthropic` — Anthropic Claude

The :class:`LLM` Protocol is intentionally minimal — a stateless
``complete(prompt, schema?) -> str``. That floor is what
:mod:`nom.doc.Extract` and :class:`nom.rag.RAG` depend on. Adapters
may add capability methods later (streaming, vision, tool-use loops)
but ``complete`` stays the contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["LLM"]


@runtime_checkable
class LLM(Protocol):
    """Adapter protocol for any LLM backend.

    Minimal contract: a stateless ``complete`` method that takes a
    prompt (and an optional JSON schema for structured output) and
    returns the model's text response.

    The ``name`` attribute is a short identifier used in logs and
    health checks (``"ollama"``, ``"openai"``, ``"anthropic"``).
    """

    name: str

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt, return the model's text response.

        When ``schema`` is provided, the returned string MUST be a
        JSON document that matches the schema. How each adapter
        achieves this differs (OpenAI uses ``response_format``
        json_schema strict mode; Anthropic uses tool-use; Ollama uses
        ``format`` json-schema constraint), but the caller sees the
        same output shape.
        """
        ...
