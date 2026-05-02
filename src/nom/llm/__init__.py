"""LLM adapters — bring your own model.

Nôm does NOT bundle a model. Pick one of the included adapters
(all implement the :class:`LLM` Protocol):

- :class:`LlamaCpp` — local inference via ``llama-server`` (no daemon
  manager; just a GGUF + a port). First-class adapter for the most
  flexible local stack.
- :class:`Ollama` — local inference (qwen3, sailor2, vistral, …) with
  built-in model management. Easiest if you don't already run
  llama.cpp.
- :class:`OpenAI` — OpenAI cloud **and** any OpenAI-compatible
  endpoint via ``base_url=`` (Azure, DeepSeek, OpenRouter, LiteLLM,
  vLLM, Together, Groq, …) — covers ~90% of hosted models without
  per-vendor SDKs.
- :class:`Anthropic` — Claude (Haiku 4.5, Sonnet 4.6, Opus 4.7).

The :class:`LLM` Protocol is a single ``complete(prompt, schema?) -> str``
method — adapters share that floor so :class:`nom.doc.Extract` and
:class:`nom.rag.RAG` can swap providers without touching call sites.

Recommended starting point for Vietnamese (per docs/pipeline.md):
``Ollama(model="qwen3:8b")``. Apache 2.0, runs on a consumer laptop.

SOTA notes (April 2026, see ``docs/sota_vn_2026q2.md`` for citations):

- **Default local**: ``ollama pull qwen3:8b`` (Apache 2.0, ~5 GB Q4).
- **VN-tuned local**: ``ollama pull sailor2:8b`` — Sailor2 is a
  13-SEA-language family from Sea-AI (Apache 2.0). Authors call it
  the strongest multilingual <10 B for SEA including Vietnamese.
- **Vision-language local**: ``ollama pull qwen3-vl:8b``.
- **Cloud cheap**: ``OpenAI(model="gpt-4o-mini")`` or
  ``Anthropic(model="claude-haiku-4-5-20251001")``.
- **Cloud headroom**: ``OpenAI(model="gpt-4o")`` /
  ``Anthropic(model="claude-opus-4-7")``.
- **Routed-via-LiteLLM-proxy**: point ``OpenAI(base_url=...)`` at any
  LiteLLM gateway URL — works with DeepSeek, Mistral, Cohere, etc.
"""

from nom.llm.anthropic import Anthropic
from nom.llm.base import LLM
from nom.llm.huggingface import HuggingFace
from nom.llm.llamacpp import LlamaCpp
from nom.llm.llamacpp_python import LlamaCppPython
from nom.llm.ollama import Ollama
from nom.llm.openai import OpenAI

__all__ = [
    "LLM",
    "Anthropic",
    "HuggingFace",
    "LlamaCpp",
    "LlamaCppPython",
    "Ollama",
    "OpenAI",
]
