"""Translation primitives — VN ↔ EN local-first.

Status: research-stage scaffold (2026-05-02). Protocol seam and
:class:`LLMTranslator` are in place so the bench harness at
``benchmarks/translation/`` can import; format walkers (docx/xlsx/pptx/
pdf) and the HF seq2seq backend land after the bench grid picks a
default model.

Design rationale and roadmap:
``docs/research/2026-05-02-translation-feature-design.md``.
Model shortlist: ``docs/research/2026-05-02-translation-models-survey.md``.
"""

from nom.translate.base import TranslationResult, Translator
from nom.translate.llm import LLMTranslator

__all__ = [
    "LLMTranslator",
    "TranslationResult",
    "Translator",
]
