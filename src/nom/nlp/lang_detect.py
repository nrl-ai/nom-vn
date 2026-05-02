"""Language detection — minimal Unicode-frequency heuristic.

A fast, dependency-free language detector good enough to route VN
vs EN vs ZH/JP/KR in a multi-language input. Production deployments
that need 100+ language coverage swap in fastText / lingua-py via
the ``nom.platform.lang_detectors`` entry point.

The heuristic scores by counting characters in language-specific
ranges:

- Vietnamese ⇒ Latin letters with VN diacritics + ``đ`` / ``Đ``
- Chinese ⇒ CJK Unified Ideographs (U+4E00..U+9FFF)
- Japanese ⇒ Hiragana (U+3040..U+309F) + Katakana (U+30A0..U+30FF)
- Korean ⇒ Hangul Syllables (U+AC00..U+D7A3)
- English ⇒ ASCII letters with no other-language signal

Output carries a confidence proportional to the dominant signal's
share of letter mass — handy for callers that want to drop
ambiguous inputs.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

__all__ = ["LanguageDetection", "detect_language"]


_VN_DIACRITIC_BASES = frozenset(
    "àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    "ÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ"
    "ÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
)


@dataclass(frozen=True, slots=True)
class LanguageDetection:
    code: str  # ISO 639-1: vi, en, zh, ja, ko, und
    confidence: float


def detect_language(text: str) -> LanguageDetection:
    """Best-effort 2-letter language code for ``text``.

    Returns ``"und"`` (undetermined) for inputs with no letter mass
    above a small threshold (e.g. all punctuation / emoji).
    """
    if not text:
        return LanguageDetection("und", confidence=0.0)

    nfc = unicodedata.normalize("NFC", text)

    counts = {"vi": 0, "en": 0, "zh": 0, "ja": 0, "ko": 0}
    total_letters = 0

    for ch in nfc:
        code = ord(ch)
        is_letter = unicodedata.category(ch).startswith("L")
        if not is_letter:
            continue
        total_letters += 1

        if 0x4E00 <= code <= 0x9FFF:
            counts["zh"] += 1
        elif 0x3040 <= code <= 0x309F or 0x30A0 <= code <= 0x30FF:
            counts["ja"] += 1
        elif 0xAC00 <= code <= 0xD7A3:
            counts["ko"] += 1
        elif ch in _VN_DIACRITIC_BASES:
            counts["vi"] += 1
        elif code <= 0x007F:
            counts["en"] += 1

    if total_letters == 0:
        return LanguageDetection("und", confidence=0.0)

    # CJK is unambiguous if any CJK chars present.
    for lang in ("zh", "ja", "ko"):
        if counts[lang] > 0:
            share = counts[lang] / total_letters
            return LanguageDetection(lang, confidence=min(1.0, share + 0.3))

    if counts["vi"] > 0:
        # Even a single VN diacritic strongly suggests VN.
        share = counts["vi"] / max(1, counts["en"] + counts["vi"])
        return LanguageDetection("vi", confidence=min(1.0, 0.5 + share / 2))

    if counts["en"] > 0:
        return LanguageDetection("en", confidence=counts["en"] / total_letters)

    return LanguageDetection("und", confidence=0.0)
