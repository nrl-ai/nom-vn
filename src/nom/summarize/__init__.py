"""Vietnamese summarization — encoder-decoder + LLM wrappers.

Today: :class:`ViT5Summarizer` (VietAI/vit5-base / vit5-large, MIT, .bin).
Public news SOTA — ROUGE-1 63.4 on vietnews per VietAI's published
benchmark; encoder-decoder caps input at 1 024 tokens, so legal
contracts may need truncation or :class:`LLMSummarizer` (forthcoming,
Tier 3 with Qwen3-8B + per-register LoRA).

Both impls take NFC-normalised input and return a frozen
:class:`SummaryResult`. The wrapper applies a register-conditional
prompt prefix when ``register`` is supplied — this is a cheap version
of register-aware summarization until the per-register LoRA path lands.
"""

from nom.summarize.vit5 import (
    Summarizer,
    SummaryResult,
    ViT5Summarizer,
)

__all__ = [
    "Summarizer",
    "SummaryResult",
    "ViT5Summarizer",
]
