"""Vietnamese text-level classifiers.

Currently exports the **register classifier** — a 4-class router that
labels VN text as ``formal`` / ``business`` / ``conversational`` /
``literary``. The motivation is downstream: VN diacritic, summarization,
and OCR-rerank checkpoints all show 5-10 pp accuracy spread across
registers, so routing each input to the right specialised checkpoint
lifts every other tool automatically.

OSS default is a zero-ML lexicon scorer (always works, ~ms latency).
For production-quality routing, register a fine-tuned PhoBERT head via
the :class:`PhoBertRegisterClassifier` wrapper or a custom Protocol
implementation. See ``docs/sota_vn_2026q2_expansion.md``.
"""

from nom.classify.register import (
    LexiconRegisterClassifier,
    PhoBertRegisterClassifier,
    RegisterClassifier,
    RegisterLabel,
    RegisterResult,
)

__all__ = [
    "LexiconRegisterClassifier",
    "PhoBertRegisterClassifier",
    "RegisterClassifier",
    "RegisterLabel",
    "RegisterResult",
]
