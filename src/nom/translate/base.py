"""Translator Protocol — the seam every backend implements.

Mirrors :mod:`nom.llm.base` in shape: minimal Protocol, real adapters
in their own modules so importing :mod:`nom.translate` stays cheap (no
``transformers`` / ``torch`` import until you instantiate
:class:`HFTranslator`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["TranslationResult", "Translator"]


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Output of a single translation call.

    ``hint_used`` records whether the backend consumed the optional
    context hint, for telemetry — specialist MT models always return
    ``False`` here.
    """

    text: str
    source_lang: str
    target_lang: str
    hint_used: bool = False


@runtime_checkable
class Translator(Protocol):
    """Adapter protocol for any translation backend.

    Stateless ``translate(text, hint?) -> str``. Format-aware callers
    (the future docx/xlsx walkers under ``nom.translate.formats``) split
    structured input into translation units, call ``translate`` per
    unit, and reassemble.

    The ``hint`` parameter carries optional context — paragraph style,
    surrounding sentence, glossary entry — that LLM-backed translators
    can fold into the prompt. Specialist seq2seq MT models ignore it.
    Keeping ``hint`` in the contract avoids a v2 API break when we add
    glossary support.
    """

    name: str
    source_lang: str
    target_lang: str

    def translate(self, text: str, *, hint: str | None = None) -> str:
        """Translate one string from ``source_lang`` to ``target_lang``.

        Implementations must NFC-normalize their output (per our
        VN normalization policy — see ``nom.text.normalize``).
        """
        ...
