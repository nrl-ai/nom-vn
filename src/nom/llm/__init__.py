"""LLM adapter interfaces.

Nôm does NOT bundle a model. Bring your own:

- :class:`Ollama` — local inference (qwen3, llama-3, vistral, etc.)
- ``OpenAI`` — gpt-4o, gpt-4-turbo (planned v0.1.1)
- ``Anthropic`` — claude-sonnet, claude-opus (planned v0.1.1)

The :class:`LLM` Protocol is a single ``complete(prompt, schema?) -> str``
method — adapters share that floor so ``Extract`` can swap providers.

Recommended starting point for Vietnamese (per docs/PIPELINE.md):
``Ollama(model="qwen3:8b")``. Apache 2.0, runs on a consumer laptop.
"""

from nom.llm.base import LLM, Anthropic, OpenAI
from nom.llm.ollama import Ollama

__all__ = ["LLM", "Anthropic", "Ollama", "OpenAI"]
