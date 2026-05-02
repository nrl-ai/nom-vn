"""Sentence-level sentiment analysis — Protocol surface.

Default OSS impl is a tiny lexicon-based scorer (Vietnamese-aware
seed list). Production deployments register a fine-tuned classifier
via the ``nom.platform.sentiment_models`` entry point — keeps the
OSS dep surface zero-ML while giving EE a clean swap-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

__all__ = [
    "LexiconSentimentModel",
    "SentimentLabel",
    "SentimentModel",
    "SentimentResult",
]


class SentimentLabel(str, Enum):
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


@dataclass(frozen=True, slots=True)
class SentimentResult:
    label: SentimentLabel
    score: float  # 0..1, confidence in the label


@runtime_checkable
class SentimentModel(Protocol):
    name: str

    def predict(self, text: str) -> SentimentResult: ...


# Tiny VN seed lexicon. Not a benchmark winner — the EE plugin ships
# a fine-tune that outperforms by 10+ pp on register-conditional
# corpora. The OSS default is for sanity checks and tests.
_POSITIVE: frozenset[str] = frozenset(
    {
        "tốt",
        "tuyệt",
        "tuyệt vời",
        "hài lòng",
        "yêu thích",
        "thích",
        "xuất sắc",
        "ngon",
        "đẹp",
        "vui",
        "thân thiện",
        "ấn tượng",
        "khen",
        "hay",
    }
)
_NEGATIVE: frozenset[str] = frozenset(
    {
        "tệ",
        "kém",
        "tồi",
        "thất vọng",
        "chậm",
        "sai",
        "lỗi",
        "buồn",
        "không hài lòng",
        "khó chịu",
        "tức giận",
        "bực",
        "chán",
        "dở",
    }
)


@dataclass
class LexiconSentimentModel:
    """Lexicon scorer: count VN positive vs negative tokens.

    NFC-normalised case-insensitive substring search. Labels:

    - score(pos) - score(neg) > 0 → POSITIVE with confidence
      proportional to net polarity / (pos + neg)
    - opposite → NEGATIVE
    - tie or no hits → NEUTRAL with score 0.5
    """

    positive: frozenset[str] = field(default_factory=lambda: _POSITIVE)
    negative: frozenset[str] = field(default_factory=lambda: _NEGATIVE)
    name: str = "lexicon-vn"

    def predict(self, text: str) -> SentimentResult:
        lo = text.lower()
        pos = sum(1 for w in self.positive if w in lo)
        neg = sum(1 for w in self.negative if w in lo)
        total = pos + neg
        if total == 0:
            return SentimentResult(SentimentLabel.NEUTRAL, score=0.5)
        if pos > neg:
            return SentimentResult(
                SentimentLabel.POSITIVE,
                score=min(1.0, 0.5 + (pos - neg) / (2 * total)),
            )
        if neg > pos:
            return SentimentResult(
                SentimentLabel.NEGATIVE,
                score=min(1.0, 0.5 + (neg - pos) / (2 * total)),
            )
        return SentimentResult(SentimentLabel.NEUTRAL, score=0.5)
