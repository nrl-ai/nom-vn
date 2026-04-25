"""Ollama LLM adapter — real implementation.

Talks to a local Ollama server via its HTTP API. We use ``httpx`` directly
rather than the ``ollama-python`` library to keep the dep surface small
and the protocol auditable. Ollama's structured-output feature (since
``ollama 0.5+``) accepts a JSON schema via the ``format`` parameter and
constrains the model's output accordingly — see
https://ollama.com/blog/structured-outputs.

Recommended local model for Vietnamese (per docs/PIPELINE.md): ``qwen3:8b``
(Apache 2.0, ~6GB Q4 VRAM). Configure with ``ollama pull qwen3:8b`` first.

This module is loaded only when the user explicitly imports it. Importing
``nom.llm`` doesn't trigger the httpx dep — see ``nom/llm/__init__.py``.
"""

from __future__ import annotations

import json
from typing import Any


class Ollama:
    """LLM adapter for a local Ollama server.

    Args:
        model: Ollama model name (must be pulled locally first via
            ``ollama pull <model>``). Default: ``qwen3:8b``.
        base_url: Ollama server URL. Default: ``http://localhost:11434``.
        timeout: HTTP timeout in seconds. Default: 120s (LLM responses
            can be slow on first call due to model load).
        temperature: Sampling temperature. Default: 0 (deterministic) for
            extraction tasks. Set higher for creative use.

    Example:
        >>> from nom.llm import Ollama
        >>> llm = Ollama(model="qwen3:8b")
        >>> llm.complete("Tóm tắt văn bản sau bằng một câu: ...")
        '...'

    Raises:
        ImportError: at construction time if httpx is not installed.
            Install with ``pip install nom-vn[llm]``.
    """

    name = "ollama"

    def __init__(
        self,
        model: str = "qwen3:8b",
        *,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        temperature: float = 0.0,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "nom.llm.Ollama requires httpx. " "Install with: pip install nom-vn[llm]"
            ) from exc
        self._httpx = httpx
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt to Ollama, return the model's text response.

        Args:
            prompt: user message.
            schema: optional JSON schema for structured output. When
                provided, Ollama constrains the response to match.
            max_tokens: ``num_predict`` — max tokens to generate.

        Returns:
            Model response as a string. If ``schema`` was provided, the
            string contains a JSON object matching the schema.
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens,
            },
        }
        if schema is not None:
            body["format"] = schema

        response = self._httpx.post(
            f"{self.base_url}/api/chat",
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        # Ollama 0.5+ chat response shape: {"message": {"role": "...", "content": "..."}}
        message = data.get("message")
        if not message or "content" not in message:
            raise RuntimeError(
                f"Unexpected Ollama response shape (missing 'message.content'): "
                f"{json.dumps(data)[:200]}"
            )
        return str(message["content"])

    def __repr__(self) -> str:
        return f"Ollama(model={self.model!r}, base_url={self.base_url!r})"
