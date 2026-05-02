"""``nom.nlp`` — Vietnamese-first NLP-as-a-service primitives.

Equivalent surface to AWS Comprehend / GCP Natural Language for VN —
without the SaaS round-trip, with reproducible benchmarks, and with
strict no-pickle / safetensors-only model loading per the project's
no-binary-RCE policy.

Modules:

- :mod:`nom.nlp.ner` — named-entity recognition (PER/ORG/LOC/MISC/…)
- :mod:`nom.nlp.sentiment` — sentence-level sentiment
- :mod:`nom.nlp.lang_detect` — language detection
- :mod:`nom.nlp.types` — shared value types

Each module exposes a Protocol surface plus at least one default
implementation. Heavy ML models are imported lazily; the module
imports cleanly on a host without ``torch`` installed and surfaces
a clear error on first use.

This package follows the same plugin pattern as :mod:`nom.platform`:
EE replacements (more accurate VN NER fine-tunes, sentiment models
trained on customer corpora) register via entry points in
``nom-vn-enterprise`` and override the OSS defaults transparently.
"""

from __future__ import annotations

from nom.nlp.lang_detect import LanguageDetection, detect_language
from nom.nlp.ner import HFNERModel, NERModel, NERSpan, RegexNERModel
from nom.nlp.sentiment import (
    LexiconSentimentModel,
    SentimentLabel,
    SentimentModel,
    SentimentResult,
)
from nom.nlp.types import NLPError

__all__ = [
    "HFNERModel",
    "LanguageDetection",
    "LexiconSentimentModel",
    "NERModel",
    "NERSpan",
    "NLPError",
    "RegexNERModel",
    "SentimentLabel",
    "SentimentModel",
    "SentimentResult",
    "detect_language",
]
