"""LLM adapter interfaces.

Nôm does NOT bundle a model. Bring your own:

- :class:`Ollama` — local inference (qwen3, llama-3, vistral, etc.)
- ``OpenAI`` — gpt-4o, gpt-4-turbo (planned v0.1.1)
- ``Anthropic`` — claude-sonnet, claude-opus (planned v0.1.1)

The :class:`LLM` Protocol is a single ``complete(prompt, schema?) -> str``
method — adapters share that floor so ``Extract`` can swap providers.

Recommended starting point for Vietnamese (per docs/pipeline.md):
``Ollama(model="qwen3:8b")``. Apache 2.0, runs on a consumer laptop.

SOTA notes (April 2026, see ``docs/sota_vn_2026q2.md`` for citations):

- **Default**: ``ollama pull qwen3:8b`` (Apache 2.0, ~5 GB Q4). Strong
  generalist; no first-party VN benchmark on the model card.
- **VN-tuned alternative**: ``ollama pull sailor2:8b`` — Sailor2 is a
  13-SEA-language family from Sea-AI (Apache 2.0, ~16 GB BF16 / ~5 GB
  Q4). Authors call it the strongest multilingual <10 B for SEA
  including Vietnamese. Source: https://sea-sailor.github.io/blog/sailor2/
- **Headroom (reasoning)**: ``ollama pull phi4`` — Microsoft Phi-4
  (14 B, MIT). Strong reasoning, no published VN benchmark — measure
  before defaulting.
- **Headroom (heavy)**: ``ollama pull deepseek-v3.2`` for highest open
  reasoning quality; ``ollama pull sailor2:20b`` for the SEA-tuned
  high tier (Apache 2.0, ~12 GB Q4).
- **Vision-language**: ``ollama pull qwen3-vl:8b`` (Apache 2.0, 32
  langs incl. VN). Future ``nom.doc`` adapter for OCR-skip document Q&A.

All work with the existing ``Ollama`` adapter — just swap ``model=``.
For hosted endpoints (OpenAI / Anthropic / DeepSeek-cloud), an
``OpenAICompatible`` adapter is planned; until then, point a
``LiteLLM`` proxy at any provider and the existing ``Ollama`` adapter
talks to it via the OpenAI-compatible wire format.
"""

from nom.llm.base import LLM, Anthropic, OpenAI
from nom.llm.ollama import Ollama

__all__ = ["LLM", "Anthropic", "Ollama", "OpenAI"]
