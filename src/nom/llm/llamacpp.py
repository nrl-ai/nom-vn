"""llama.cpp LLM adapter — wraps llama-server's HTTP API.

llama.cpp ships ``llama-server``, an inference server that exposes an
OpenAI-compatible ``/v1/chat/completions`` endpoint. This adapter is a
thin wrapper that calls it directly so users don't have to detour
through environment-variable plumbing on the OpenAI adapter.

Why ship a dedicated adapter when ``OpenAI(base_url=...)`` already
works against llama-server?

- **Discovery.** Most users don't know llama-server speaks OpenAI's
  wire format. A first-class ``LlamaCpp`` import surfaces the option.
- **No fake API key.** llama-server doesn't validate the bearer token;
  the OpenAI adapter requires one. Setting ``api_key="not-needed"`` is
  awkward boilerplate. This adapter just doesn't send the header.
- **Better error messages.** When llama-server isn't running, the
  error mentions llama.cpp specifically — easier to act on.

Example::

    # 1. (one-time) install llama.cpp; download a GGUF; start the server
    #    brew install llama.cpp  # or apt / scoop / cargo
    #    llama-server -m ./qwen2.5-7b-instruct-q4_k_m.gguf --port 8081

    from nom.llm import LlamaCpp
    llm = LlamaCpp(base_url="http://127.0.0.1:8081/v1")
    print(llm.complete("Tóm tắt văn bản sau bằng một câu: ..."))

The ``model`` field is included in requests but llama-server ignores
it — the GGUF passed to ``-m`` is what runs. We keep it so logs read
sensibly.
"""

from __future__ import annotations

import json
import os
from typing import Any


class LlamaCpp:
    """LLM adapter for a running llama-server (llama.cpp).

    Args:
        model: human-readable model name to record in requests/logs.
            llama-server itself ignores this — the GGUF passed via
            ``-m`` is what runs. Default ``"llamacpp"``.
        base_url: HTTP root that the llama-server is listening on.
            Default ``http://127.0.0.1:8080/v1``. Use the value from
            ``--host`` + ``--port`` you launched llama-server with;
            don't forget the ``/v1`` suffix (some setups omit it).
            Override with ``NOM_LLAMACPP_URL`` env var.
        timeout: HTTP timeout in seconds. Default 300s — local CPU
            inference on a 7B-Q4 model can take 60-120s for a 512-tok
            response on a laptop without a GPU.
        temperature: Sampling temperature. Default 0 (deterministic)
            for extraction; raise for creative tasks.

    Raises:
        ImportError: if httpx is not installed (``pip install nom-vn[llm]``).
    """

    name = "llamacpp"

    def __init__(
        self,
        model: str = "llamacpp",
        *,
        base_url: str | None = None,
        timeout: float = 300.0,
        temperature: float = 0.0,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "nom.llm.LlamaCpp requires httpx. Install with: pip install nom-vn[llm]"
            ) from exc

        url: str = base_url or os.environ.get("NOM_LLAMACPP_URL") or "http://127.0.0.1:8080/v1"
        self._httpx = httpx
        self.model = model
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt, return the model's text response.

        When ``schema`` is provided we pass it via the OpenAI-compatible
        ``response_format`` field. llama-server (≥b3950) honours JSON
        schema; older builds fall back to free-form generation. We
        don't validate the response shape here — :class:`nom.doc.Extract`
        does that downstream.
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "nom_extract", "schema": schema},
            }

        try:
            response = self._httpx.post(
                f"{self.base_url}/chat/completions",
                json=body,
                timeout=self.timeout,
            )
        except Exception as exc:
            cls = type(exc).__name__
            if "ConnectError" in cls or "ConnectTimeout" in cls:
                raise RuntimeError(
                    "Could not reach llama-server at "
                    f"{self.base_url}. Start it with: "
                    "`llama-server -m <gguf-path> --host 127.0.0.1 --port 8080`"
                ) from exc
            raise

        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") or []
        if not choices or "message" not in choices[0]:
            raise RuntimeError(
                "Unexpected llama-server response shape (missing 'choices[0].message'): "
                f"{json.dumps(data)[:200]}"
            )
        content = choices[0]["message"].get("content")
        if content is None:
            raise RuntimeError("llama-server returned empty content")
        return str(content)

    def __repr__(self) -> str:
        return f"LlamaCpp(model={self.model!r}, base_url={self.base_url!r})"


__all__ = ["LlamaCpp"]
