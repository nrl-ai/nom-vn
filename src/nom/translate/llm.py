"""LLM-backed translator.

Wraps any :class:`nom.llm.LLM` (Ollama, OpenAI, Anthropic) as a
:class:`Translator`. Uses a JSON-structured-output prompt to suppress
the rambling failure mode that affects generic chat LLMs on translation
tasks.

Default model is whatever the caller passes — the bench harness at
``benchmarks/translation/bench_translation_flores.py`` is what tells
us which to recommend. Until that lands its baseline JSONs, this class
intentionally has no default model.
"""

from __future__ import annotations

import json
import unicodedata
from typing import Any

from nom.llm.base import LLM
from nom.translate.base import Translator

__all__ = ["LLMTranslator"]


_LANG_NAMES: dict[str, str] = {
    "en": "English",
    "vi": "Vietnamese",
    "zh": "Chinese (Mandarin)",
    "ko": "Korean",
    "ja": "Japanese",
}


class LLMTranslator(Translator):
    """Translate via a generic chat LLM with JSON-structured output.

    Example::

        from nom.llm import Ollama
        from nom.translate import LLMTranslator

        llm = Ollama(model="qwen3:8b", think=False)
        tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
        tx.translate("This contract is void.")
        # → "Hợp đồng này vô hiệu."
    """

    name = "llm"

    def __init__(
        self,
        *,
        llm: LLM,
        source_lang: str,
        target_lang: str,
        max_tokens: int = 1024,
    ) -> None:
        if source_lang not in _LANG_NAMES or target_lang not in _LANG_NAMES:
            raise ValueError(
                f"unsupported language pair: {source_lang}->{target_lang}; "
                f"v0.1 supports {sorted(_LANG_NAMES)}"
            )
        if source_lang == target_lang:
            raise ValueError("source_lang and target_lang must differ")
        self._llm = llm
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._max_tokens = max_tokens

    def translate(self, text: str, *, hint: str | None = None) -> str:
        if not text or not text.strip():
            return text
        prompt = self._build_prompt(text, hint)
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {"translation": {"type": "string"}},
            "required": ["translation"],
        }
        raw = self._llm.complete(prompt, schema=schema, max_tokens=self._max_tokens)
        out = self._extract_translation(raw)
        return unicodedata.normalize("NFC", out)

    def _build_prompt(self, text: str, hint: str | None) -> str:
        src = _LANG_NAMES[self.source_lang]
        tgt = _LANG_NAMES[self.target_lang]
        hint_block = f"\nContext hint: {hint}" if hint else ""
        return (
            f"Translate the following {src} text into {tgt}. Preserve "
            f"meaning, tone, and proper nouns. Return only the "
            f"translation as JSON with a single field 'translation'."
            f"{hint_block}\n\n"
            f"Source ({src}): {text}"
        )

    @staticmethod
    def _extract_translation(raw: str) -> str:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return _strip_thinking_directives(raw.strip())
        if isinstance(obj, dict):
            value = obj.get("translation")
            if isinstance(value, str):
                return _strip_thinking_directives(value.strip())
        return _strip_thinking_directives(raw.strip())


# Qwen3 occasionally leaks the chat-template directive (/no_think, /think)
# back into the generated JSON `translation` field — we caught
# `"Project code /no_think"` on a real XLSX cell. Strip them here.
_THINK_DIRECTIVES = (" /no_think", " /think", "/no_think", "/think")


def _strip_thinking_directives(text: str) -> str:
    for d in _THINK_DIRECTIVES:
        text = text.replace(d, "")
    # Also drop any stray Qwen3 thinking-block remnants — see the same
    # pattern in nom.text.normalize.
    if "</think>" in text:
        text = text.split("</think>", 1)[1].lstrip()
    return text.strip()
