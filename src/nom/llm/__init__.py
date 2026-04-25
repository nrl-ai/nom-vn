"""LLM adapter interfaces — preview API for v0.1.

Nôm does NOT bundle a model. Bring your own:
    - Ollama: run open models locally (qwen3, llama-3, vistral)
    - OpenAI: gpt-4o, gpt-4-turbo
    - Anthropic: claude-sonnet, claude-opus

The goal is one interface so you can swap providers without changing
extraction code. Adapters in v0.1 will be thin wrappers around the
official SDKs, with a ``complete(prompt, schema?) -> str`` shape.
"""

from nom.llm.base import LLM, Anthropic, Ollama, OpenAI

__all__ = ["LLM", "Anthropic", "Ollama", "OpenAI"]
