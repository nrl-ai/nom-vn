"""In-process llama.cpp via the ``llama-cpp-python`` bindings.

Sister to :class:`nom.llm.LlamaCpp` (which talks to a separate
``llama-server`` process over HTTP). This adapter calls into
llama.cpp directly through the Python bindings — no daemon, no port,
no second process to babysit.

When to pick this over Ollama / LlamaCpp:

- You don't want a background daemon (Ollama) or a separate server
  process (llama-server).
- You want maximum speed by skipping the localhost HTTP roundtrip.
- You want HF-Hub auto-download for GGUFs without writing an
  ``ollama pull`` shell command first.

When NOT to pick it:

- You want to share one model across multiple Python processes
  (HTTP adapters do this for free; in-process forces one model
  per Python interpreter).
- You're on a platform where ``llama-cpp-python`` won't compile
  (it builds C++ on install on most non-prebuilt platforms).

Pulling models from HuggingFace is automatic — pass an HF repo id
and filename via :meth:`Llama.from_pretrained` shorthand using
``model="hf:repo:filename"``::

    from nom.llm import LlamaCppPython
    llm = LlamaCppPython(model="hf:bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M")
    print(llm.complete("Tóm tắt văn bản sau: ..."))

Or pass a local GGUF path::

    llm = LlamaCppPython(model="./models/qwen2.5-7b-instruct-q4_k_m.gguf")
"""

from __future__ import annotations

from typing import Any


class LlamaCppPython:
    """In-process llama.cpp adapter.

    Args:
        model: either a local GGUF file path, or ``"hf:<repo>:<filename>"``
            shorthand to auto-download from the HuggingFace Hub. Filename
            can include glob (e.g. ``Q4_K_M``) — the binding picks the
            best match.
        n_ctx: context window in tokens. Default 8192.
        n_gpu_layers: layers to offload to GPU. ``-1`` = all (the
            default), ``0`` = CPU only.
        temperature: sampling temperature. Default 0 (deterministic).
        verbose: passed through to ``Llama(...)`` — set ``True`` for
            llama.cpp's chatty load output.

    Raises:
        ImportError: at construction if ``llama-cpp-python`` is not
            installed (``pip install nom-vn[llamacpp-python]``).
    """

    name = "llamacpp-python"

    def __init__(
        self,
        model: str,
        *,
        n_ctx: int = 8192,
        n_gpu_layers: int = -1,
        temperature: float = 0.0,
        verbose: bool = False,
    ) -> None:
        try:
            import llama_cpp
        except ImportError as exc:
            raise ImportError(
                "nom.llm.LlamaCppPython requires llama-cpp-python. "
                'Install with: pip install "nom-vn[llamacpp-python]" '
                "OR: pip install llama-cpp-python"
            ) from exc

        self.model_spec = model
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.temperature = temperature
        self.verbose = verbose
        self._llama = llama_cpp
        self._llm: Any = None

    @property
    def model(self) -> str:
        return self.model_spec

    def _ensure_loaded(self) -> None:
        if self._llm is not None:
            return
        from llama_cpp import Llama

        if self.model_spec.startswith("hf:"):
            # Format: hf:<repo>:<filename-or-glob>
            _, rest = self.model_spec.split(":", 1)
            try:
                repo, filename = rest.split(":", 1)
            except ValueError as exc:
                raise ValueError(
                    "HF model spec must be 'hf:<repo>:<filename>', got "
                    f"{self.model_spec!r}. Example: hf:bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"
                ) from exc
            self._llm = Llama.from_pretrained(
                repo_id=repo,
                filename=filename,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose,
            )
        else:
            self._llm = Llama(
                model_path=self.model_spec,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose,
            )

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt, return the model's continuation."""
        self._ensure_loaded()
        kwargs: dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        if schema is not None:
            # llama-cpp-python supports response_format with type "json_object"
            # and the json schema via grammar. We pass through the OpenAI-
            # compatible shape that newer versions accept.
            kwargs["response_format"] = {
                "type": "json_object",
                "schema": schema,
            }
        out = self._llm.create_chat_completion(**kwargs)
        choices = out.get("choices") or []
        if not choices:
            raise RuntimeError(f"llama-cpp-python returned no choices: {out!r}")
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if content is None:
            raise RuntimeError("llama-cpp-python returned empty content")
        return str(content)

    def __repr__(self) -> str:
        return f"LlamaCppPython(model={self.model_spec!r})"


__all__ = ["LlamaCppPython"]
