"""OpenAI / OpenAI-compatible LLM adapter.

Talks to the OpenAI Chat Completions API via ``httpx``. The adapter
also covers any OpenAI-compatible endpoint — pass ``base_url`` to point
at Azure OpenAI, DeepSeek, OpenRouter, LiteLLM, vLLM, Together, Groq,
or any other provider that speaks the same wire format. That covers
~90% of hosted LLMs in 2026 without a per-vendor SDK.

Structured output uses the official ``response_format`` JSON-schema
contract (https://platform.openai.com/docs/guides/structured-outputs)
when ``schema=`` is passed — the model is constrained to emit valid
JSON matching the schema, so ``Extract`` doesn't need to hand-parse.

This module is loaded only when the user imports it. Plain
``import nom.llm`` does not trigger the httpx dep.
"""

from __future__ import annotations

import json
import os
from typing import Any


class OpenAI:
    """LLM adapter for OpenAI and OpenAI-compatible endpoints.

    Args:
        model: model name. Default: ``gpt-4o-mini`` — cheapest 4o-class
            model, sane default for extraction. Override with
            ``gpt-4o``, ``gpt-4-turbo``, or any vendor-specific name
            when pointing ``base_url`` elsewhere.
        api_key: API key. Falls back to the ``OPENAI_API_KEY``
            environment variable when omitted.
        base_url: API root. Default OpenAI's. Point at any OpenAI-
            compatible endpoint (Azure, DeepSeek, OpenRouter, LiteLLM,
            vLLM, Together, Groq, …) without changing call sites.
        timeout: HTTP timeout in seconds. Default 120s — first-token
            latency on hosted models can be 5-20s under load.
        temperature: Sampling temperature. Default 0 (deterministic)
            for extraction; raise for creative tasks.
        organization: optional ``OpenAI-Organization`` header value.

    Example:
        >>> from nom.llm import OpenAI
        >>> llm = OpenAI(model="gpt-4o-mini")  # picks up OPENAI_API_KEY
        >>> llm.complete("Tóm tắt văn bản sau bằng một câu: ...")
        '...'

        Pointing at DeepSeek (OpenAI-compatible) instead::

            llm = OpenAI(
                model="deepseek-chat",
                base_url="https://api.deepseek.com/v1",
                api_key="sk-...",
            )

    Raises:
        ImportError: at construction time if httpx is not installed
            (``pip install nom-vn[llm]``).
        RuntimeError: at construction time if no API key is available
            (constructor argument or ``OPENAI_API_KEY`` env var).
    """

    name = "openai"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
        temperature: float = 0.0,
        organization: str | None = None,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "nom.llm.OpenAI requires httpx. Install with: pip install nom-vn[llm]"
            ) from exc

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("nom.llm.OpenAI: no API key. Pass api_key= or set OPENAI_API_KEY.")

        self._httpx = httpx
        self._api_key = key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.organization = organization

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt, return the model's text response.

        When ``schema`` is provided we set ``response_format`` to
        ``json_schema`` with ``strict: true`` so the model is
        constrained to emit valid JSON matching the schema. The
        returned string is that JSON document.
        """
        # gpt-5* and o-series models reject `max_tokens` in favour of
        # `max_completion_tokens` (and reject `temperature` other than 1).
        # Detect by model id prefix so the adapter remains a single class.
        uses_completion_tokens = self.model.startswith(("gpt-5", "o1", "o3", "o4"))
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if uses_completion_tokens:
            body["max_completion_tokens"] = max_tokens
        else:
            body["temperature"] = self.temperature
            body["max_tokens"] = max_tokens
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "nom_extract", "strict": True, "schema": schema},
            }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization

        response = self._httpx.post(
            f"{self.base_url}/chat/completions",
            json=body,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") or []
        if not choices or "message" not in choices[0]:
            raise RuntimeError(
                f"Unexpected OpenAI response shape (missing 'choices[0].message'): "
                f"{json.dumps(data)[:200]}"
            )
        content = choices[0]["message"].get("content")
        if content is None:
            raise RuntimeError(
                f"OpenAI response had no content (refusal? finish_reason="
                f"{choices[0].get('finish_reason')!r})."
            )
        return str(content)

    def __repr__(self) -> str:
        return f"OpenAI(model={self.model!r}, base_url={self.base_url!r})"
