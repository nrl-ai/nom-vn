"""Anthropic Claude LLM adapter.

Talks to the Anthropic Messages API via ``httpx``. Mirrors the shape
of :class:`nom.llm.OpenAI` so call sites can swap providers by
constructor swap alone — both implement the :class:`nom.llm.LLM`
Protocol's ``complete`` method.

Structured output is achieved via the **tool use** pattern (Anthropic's
recommended path for guaranteed-shape JSON): when ``schema`` is given,
we register a single synthetic tool whose ``input_schema`` is the
caller's schema and force ``tool_choice`` to it. The returned string
is the JSON of the tool input. See:
https://docs.anthropic.com/en/docs/build-with-claude/tool-use

This module is loaded only when the user imports it. Plain
``import nom.llm`` does not trigger the httpx dep.
"""

from __future__ import annotations

import json
import os
from typing import Any


class Anthropic:
    """LLM adapter for Anthropic's Claude models.

    Args:
        model: model name. Default ``claude-haiku-4-5-20251001`` —
            cheapest 4.5-class Claude, sane default for extraction.
            For headroom use ``claude-sonnet-4-6`` or
            ``claude-opus-4-7``.
        api_key: API key. Falls back to the ``ANTHROPIC_API_KEY``
            environment variable when omitted.
        base_url: API root. Default Anthropic's official endpoint.
            Override for self-hosted or proxied gateways.
        timeout: HTTP timeout in seconds. Default 120s.
        temperature: Sampling temperature. Default 0 (deterministic)
            for extraction; raise for creative tasks.
        anthropic_version: API version header. Default
            ``2023-06-01`` (the current stable as of 2026Q2).

    Example:
        >>> from nom.llm import Anthropic
        >>> llm = Anthropic(model="claude-haiku-4-5-20251001")
        >>> llm.complete("Tóm tắt văn bản sau bằng một câu: ...")
        '...'

    Raises:
        ImportError: at construction time if httpx is not installed
            (``pip install nom-vn[llm]``).
        RuntimeError: at construction time if no API key is available
            (constructor argument or ``ANTHROPIC_API_KEY`` env var).
    """

    name = "anthropic"

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        *,
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com",
        timeout: float = 120.0,
        temperature: float = 0.0,
        anthropic_version: str = "2023-06-01",
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "nom.llm.Anthropic requires httpx. Install with: pip install nom-vn[llm]"
            ) from exc

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "nom.llm.Anthropic: no API key. Pass api_key= or set ANTHROPIC_API_KEY."
            )

        self._httpx = httpx
        self._api_key = key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.anthropic_version = anthropic_version

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt, return the model's text response.

        When ``schema`` is provided we use Anthropic's tool-use pattern
        with a single forced tool — the returned string is the tool's
        ``input`` as JSON, guaranteed to match ``schema``.
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if schema is not None:
            tool_name = "nom_extract"
            body["tools"] = [
                {
                    "name": tool_name,
                    "description": "Return a JSON object matching the requested schema.",
                    "input_schema": schema,
                }
            ]
            body["tool_choice"] = {"type": "tool", "name": tool_name}

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }

        response = self._httpx.post(
            f"{self.base_url}/v1/messages",
            json=body,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        content = data.get("content") or []
        if schema is not None:
            # Tool-use: pull the single forced tool_use block, return its input as JSON.
            for block in content:
                if block.get("type") == "tool_use":
                    return json.dumps(block.get("input", {}), ensure_ascii=False)
            raise RuntimeError(
                f"Anthropic response had no tool_use block (stop_reason="
                f"{data.get('stop_reason')!r}): {json.dumps(data)[:200]}"
            )
        # Regular completion: concatenate text blocks (almost always one).
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        if not texts:
            raise RuntimeError(
                f"Anthropic response had no text content (stop_reason="
                f"{data.get('stop_reason')!r}): {json.dumps(data)[:200]}"
            )
        return "".join(texts)

    def __repr__(self) -> str:
        return f"Anthropic(model={self.model!r}, base_url={self.base_url!r})"
