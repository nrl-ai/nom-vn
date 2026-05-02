"""HuggingFace transformers in-process LLM adapter.

Loads any HF text-generation model directly via ``transformers`` —
no Ollama daemon, no llama-server, no HTTP roundtrip. Trade-off vs the
HTTP adapters: heavier install (torch + transformers, ~2 GB total)
and the model lives in this Python process's memory (no swap-out
without restart).

When to pick this over Ollama / llama.cpp:

- You already have transformers + torch installed (e.g. for the HF
  diacritic-restoration models nom ships) and don't want a second
  inference server.
- You want a HuggingFace model that doesn't ship as GGUF (e.g. raw
  safetensors-only checkpoints).
- You want deterministic Python-only deployment (no daemon to
  babysit).

Pulling models from HuggingFace is automatic on first use: pass any
HF model id as ``model=`` and ``transformers`` will download +
cache it under ``~/.cache/huggingface/``.

Example::

    from nom.llm import HuggingFace
    llm = HuggingFace(model="Qwen/Qwen2.5-7B-Instruct")
    print(llm.complete("Tóm tắt văn bản sau: ..."))

Quantization: pass ``load_in_4bit=True`` (requires ``bitsandbytes``)
to load int4 — fits a 7B model in <5 GB VRAM. Otherwise the model
loads in fp16 on CUDA, fp32 on CPU.

Schema (structured-output) requests fall back to free-form generation
because vanilla ``transformers.generate`` doesn't constrain to a JSON
schema. For schema-constrained extraction, prefer the Ollama or
LlamaCpp adapters which support ``response_format``.
"""

from __future__ import annotations

from typing import Any


class HuggingFace:
    """In-process HF transformers LLM adapter.

    Args:
        model: HuggingFace model id (e.g. ``Qwen/Qwen2.5-7B-Instruct``).
            Auto-downloads on first call.
        device: ``"cpu"``, ``"cuda"``, or ``"auto"`` (default — picks
            CUDA when available else CPU). MPS is not auto-selected
            (some quantized kernels are still flaky on Apple Silicon).
        max_input_tokens: Truncate prompts longer than this. Default
            4096; raise if your model's context allows.
        temperature: Sampling temperature. Default 0 (greedy
            deterministic).
        load_in_4bit: int4 quantization via bitsandbytes. Requires
            ``pip install bitsandbytes`` and a CUDA device.
        trust_remote_code: pass-through to ``from_pretrained``. Default
            False — only enable for repos you've audited.

    Raises:
        ImportError: at construction if torch + transformers are not
            installed (``pip install nom-vn[llm-hf]``).
    """

    name = "huggingface"

    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-3B-Instruct",
        *,
        device: str = "auto",
        max_input_tokens: int = 4096,
        temperature: float = 0.0,
        load_in_4bit: bool = False,
        trust_remote_code: bool = False,
    ) -> None:
        try:
            import torch
            import transformers  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "nom.llm.HuggingFace requires torch + transformers. "
                'Install with: pip install "nom-vn[llm-hf]" '
                'OR: pip install "transformers<5" torch'
            ) from exc

        self.model_id = model
        self.max_input_tokens = max_input_tokens
        self.temperature = temperature
        self.load_in_4bit = load_in_4bit
        self.trust_remote_code = trust_remote_code
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self._torch = torch
        self._tok: Any = None
        self._model: Any = None

    @property
    def model(self) -> str:
        """Backwards-compat alias — most adapters expose ``.model``."""
        return self.model_id

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tok = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call,unused-ignore]
            self.model_id, trust_remote_code=self.trust_remote_code
        )
        kwargs: dict[str, Any] = {"trust_remote_code": self.trust_remote_code}
        if self.load_in_4bit:
            try:
                from transformers import BitsAndBytesConfig

                kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)  # type: ignore[no-untyped-call,unused-ignore]
            except ImportError as exc:
                raise ImportError(
                    "load_in_4bit=True requires bitsandbytes. "
                    "Install with: pip install bitsandbytes"
                ) from exc
        else:
            kwargs["dtype"] = self._torch.float16 if self.device == "cuda" else self._torch.float32

        m = AutoModelForCausalLM.from_pretrained(self.model_id, **kwargs)
        if not self.load_in_4bit:
            m = m.to(self.device)  # type: ignore[arg-type,unused-ignore]
        m.eval()  # type: ignore[no-untyped-call,unused-ignore]
        self._model = m

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt; return the model's continuation.

        ``schema`` is accepted for API compatibility but ignored — vanilla
        transformers.generate doesn't constrain output to a JSON schema.
        Use Ollama / LlamaCpp adapters when you need schema enforcement.
        """
        del schema  # documented as ignored
        self._ensure_loaded()
        # Apply chat template when available — most modern instruct models
        # expect this; raw text input will work but degrades quality.
        messages = [{"role": "user", "content": prompt}]
        if hasattr(self._tok, "apply_chat_template"):
            try:
                input_ids = self._tok.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_tensors="pt",
                )
            except Exception:
                input_ids = self._tok(prompt, return_tensors="pt").input_ids
        else:
            input_ids = self._tok(prompt, return_tensors="pt").input_ids

        if self.max_input_tokens and input_ids.shape[1] > self.max_input_tokens:
            input_ids = input_ids[:, -self.max_input_tokens :]
        input_ids = input_ids.to(self.device)

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": max_tokens,
            "pad_token_id": getattr(self._tok, "eos_token_id", None) or 0,
        }
        if self.temperature > 0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = self.temperature
        else:
            gen_kwargs["do_sample"] = False

        with self._torch.no_grad():
            out = self._model.generate(input_ids, **gen_kwargs)

        # Slice off the prompt tokens; decode only the generated continuation.
        generated = out[0, input_ids.shape[1] :]
        text = self._tok.decode(generated, skip_special_tokens=True)
        return str(text).strip()

    def __repr__(self) -> str:
        return f"HuggingFace(model={self.model_id!r}, device={self.device!r})"


__all__ = ["HuggingFace"]
