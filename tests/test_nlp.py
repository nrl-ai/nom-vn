"""Tests for ``nom.nlp`` — NER (regex baseline + HF guard) + sentiment +
language detection.
"""

from __future__ import annotations

import pytest

from nom.nlp import (
    HFNERModel,
    LexiconSentimentModel,
    NERModel,
    NERSpan,
    NLPError,
    RegexNERModel,
    SentimentLabel,
    SentimentModel,
    detect_language,
)
from nom.nlp.sentiment import LexiconSentimentModel as _LexImpl

# ---- NER: Protocol + regex baseline ---------------------------------


def test_regex_ner_satisfies_protocol() -> None:
    assert isinstance(RegexNERModel(), NERModel)


def test_regex_ner_money() -> None:
    spans = RegexNERModel().tag("Tổng cộng 1.500.000 VND.")
    assert any(s.label == "MONEY" and "1.500.000" in s.text for s in spans)


def test_regex_ner_iso_date() -> None:
    spans = RegexNERModel().tag("Hợp đồng ký ngày 2026-05-02.")
    assert any(s.label == "DATE" and s.text == "2026-05-02" for s in spans)


def test_regex_ner_vn_date_format() -> None:
    spans = RegexNERModel().tag("Hợp đồng ký ngày 02/05/2026.")
    assert any(s.label == "DATE" and s.text == "02/05/2026" for s in spans)


def test_regex_ner_known_org() -> None:
    spans = RegexNERModel().tag("Khách hàng VCB và FPT.")
    labels = {s.label for s in spans}
    assert "ORG" in labels
    orgs = {s.text for s in spans if s.label == "ORG"}
    assert {"VCB", "FPT"} <= orgs


def test_regex_ner_extra_patterns() -> None:
    extra = (("PER", r"\b(?:Nguyễn|Lê)\s+\w+"),)
    model = RegexNERModel(extra_patterns=extra)
    spans = model.tag("Bà Nguyễn Vân và ông Lê Anh.")
    pers = [s for s in spans if s.label == "PER"]
    assert len(pers) == 2


def test_regex_ner_overlap_resolution() -> None:
    # Custom overlapping patterns: longer span wins.
    extra = (
        ("LOC", r"Hà Nội"),
        ("LOC", r"Hà Nội thủ đô"),
    )
    spans = RegexNERModel(extra_patterns=extra).tag("Tôi sống ở Hà Nội thủ đô")
    assert len([s for s in spans if s.label == "LOC"]) == 1
    assert spans[-1].text == "Hà Nội thủ đô"


# ---- HFNERModel guard rails -----------------------------------------


def test_hf_ner_refuses_bin_only_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the HF repo has no safetensors, the loader refuses unless
    ``allow_bin=True`` is explicitly set."""
    from nom.nlp import ner as ner_mod

    monkeypatch.setattr(ner_mod, "_safetensors_available", lambda model_id: False)
    model = HFNERModel(model_id="some-org/legacy-bin-only")
    with pytest.raises(NLPError, match=r"no model\.safetensors"):
        model.tag("test")


def test_hf_ner_clear_error_when_transformers_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If torch/transformers aren't installed, the load surfaces a
    clear NLPError rather than ImportError."""
    from nom.nlp import ner as ner_mod

    monkeypatch.setattr(ner_mod, "_safetensors_available", lambda model_id: True)

    class _ImportFailingPipeline:
        @staticmethod
        def __call__(*_a, **_kw):
            raise ImportError("transformers not available")

    # Patch the import inside _load — simulate transformers missing.
    import sys

    monkeypatch.setitem(sys.modules, "transformers", None)
    model = HFNERModel(model_id="some/model")
    with pytest.raises(NLPError, match="transformers is required"):
        model.tag("anything")


# ---- Sentiment ------------------------------------------------------


def test_lexicon_sentiment_satisfies_protocol() -> None:
    assert isinstance(LexiconSentimentModel(), SentimentModel)


def test_lexicon_sentiment_positive() -> None:
    r = LexiconSentimentModel().predict("Sản phẩm này rất tuyệt vời, tôi rất hài lòng.")
    assert r.label is SentimentLabel.POSITIVE
    assert r.score > 0.5


def test_lexicon_sentiment_negative() -> None:
    r = LexiconSentimentModel().predict("Dịch vụ tệ quá, rất thất vọng.")
    assert r.label is SentimentLabel.NEGATIVE
    assert r.score > 0.5


def test_lexicon_sentiment_neutral_on_empty() -> None:
    r = LexiconSentimentModel().predict("Hôm nay trời mưa, tôi đi học.")
    assert r.label is SentimentLabel.NEUTRAL


def test_lexicon_sentiment_tie_returns_neutral() -> None:
    r = LexiconSentimentModel().predict("Đẹp nhưng tệ.")
    # 1 pos + 1 neg → NEUTRAL
    assert r.label is SentimentLabel.NEUTRAL


# ---- Language detection ---------------------------------------------


def test_detect_vn() -> None:
    out = detect_language("Đây là một câu tiếng Việt.")
    assert out.code == "vi"
    assert out.confidence > 0.5


def test_detect_en() -> None:
    out = detect_language("This is a plain English sentence.")
    assert out.code == "en"


def test_detect_zh() -> None:
    out = detect_language("这是中文。")
    assert out.code == "zh"


def test_detect_ja() -> None:
    out = detect_language("これは日本語です。")
    # Japanese mixes hiragana/katakana with kanji; either ja or zh
    # is acceptable as long as it's CJK-correct (most likely ja
    # since hiragana count > kanji count in this short sentence).
    assert out.code in {"ja", "zh"}


def test_detect_ko() -> None:
    out = detect_language("안녕하세요, 베트남.")
    assert out.code == "ko"


def test_detect_undetermined_on_punctuation_only() -> None:
    out = detect_language("!!! ??? ...")
    assert out.code == "und"
    assert out.confidence == 0.0


def test_detect_empty_input() -> None:
    assert detect_language("").code == "und"


# Smoke: surface checks
def test_lexiconsentimentmodel_alias_consistent() -> None:
    assert _LexImpl is LexiconSentimentModel


def test_nerspan_is_frozen() -> None:
    s = NERSpan(0, 5, "ORG", "FPT.AI")
    with pytest.raises(AttributeError, match="cannot assign"):
        s.label = "PER"  # type: ignore[misc]
