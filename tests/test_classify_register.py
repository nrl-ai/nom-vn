"""Unit tests for nom.classify.register.

Lexicon classifier only — PhoBERT wrapper has its own integration test
once the trained checkpoint is published. Lexicon tests pin the class
boundaries (FORMAL legal prose, BUSINESS news, CONVERSATIONAL forum
post, LITERARY classical) and verify the no-marker fallback to BUSINESS.
"""

from __future__ import annotations

import pytest

from nom.classify import (
    LexiconRegisterClassifier,
    PhoBertRegisterClassifier,
    RegisterClassifier,
    RegisterLabel,
)


@pytest.fixture
def clf() -> LexiconRegisterClassifier:
    return LexiconRegisterClassifier()


def test_lexicon_satisfies_protocol(clf: LexiconRegisterClassifier) -> None:
    # Runtime-checkable Protocol — confirms wrapper meets the seam shape.
    assert isinstance(clf, RegisterClassifier)
    assert clf.name == "lexicon-vn-register"


def test_formal_legal_prose(clf: LexiconRegisterClassifier) -> None:
    text = (
        "Căn cứ Luật ban hành văn bản quy phạm pháp luật, "
        "Bộ Tư pháp trân trọng kính gửi quý cơ quan thông tư có hiệu lực "
        "từ ngày 01/01/2026."
    )
    result = clf.predict(text)
    assert result.label is RegisterLabel.FORMAL
    assert 0.4 <= result.score <= 1.0
    # Distribution sums to ~1
    total = sum(result.distribution.values())
    assert abs(total - 1.0) < 1e-6


def test_business_news_lead(clf: LexiconRegisterClassifier) -> None:
    text = (
        "Doanh thu công ty trong quý 2 năm 2026 đạt 1.2 tỷ đồng, "
        "tăng 18% so với cùng kỳ năm trước. Cổ phiếu lên 12% sau báo cáo."
    )
    result = clf.predict(text)
    assert result.label is RegisterLabel.BUSINESS


def test_conversational_forum(clf: LexiconRegisterClassifier) -> None:
    text = "Mình thấy chỗ đó ngon lắm nha, bạn ơi đi thử đi vậy nhé!"
    result = clf.predict(text)
    assert result.label is RegisterLabel.CONVERSATIONAL


def test_literary_classical(clf: LexiconRegisterClassifier) -> None:
    text = (
        "Thuở xưa, chàng cùng nàng dạo bước dưới bóng nguyệt, "
        "lệ rơi giữa non sông bốn bể. Nỗi niềm tao nhân mặc khách "
        "mãi vương vấn ngày xưa."
    )
    result = clf.predict(text)
    assert result.label is RegisterLabel.LITERARY


def test_no_markers_falls_back_to_business(clf: LexiconRegisterClassifier) -> None:
    # Plain neutral prose with no register markers — uniform distribution,
    # label = BUSINESS (the safe default).
    text = "Hôm nay trời đẹp."
    result = clf.predict(text)
    assert result.label is RegisterLabel.BUSINESS
    # Uniform: each class at 0.25
    for v in result.distribution.values():
        assert abs(v - 0.25) < 1e-6
    assert abs(result.score - 0.25) < 1e-6


def test_nfc_robustness(clf: LexiconRegisterClassifier) -> None:
    """NFD input must classify same as NFC — `normalize` runs inside predict.

    "Nghị định" composed (NFC) vs decomposed (NFD) — both must hit the
    formal marker.
    """
    import unicodedata

    nfc = "Theo nghị định, các bên cam kết thực hiện."
    nfd = unicodedata.normalize("NFD", nfc)
    a = clf.predict(nfc)
    b = clf.predict(nfd)
    assert a.label is RegisterLabel.FORMAL
    assert b.label is RegisterLabel.FORMAL
    # Scores should be identical because normalization happens internally.
    assert abs(a.score - b.score) < 1e-9


def test_phobert_wrapper_raises_without_model_id() -> None:
    """Default model id is None until training run completes — instantiating
    without an explicit model_id should fail loud, not silent."""
    clf = PhoBertRegisterClassifier()
    with pytest.raises(RuntimeError, match="model_id"):
        clf.predict("test")


def test_distribution_sums_to_one_when_markers_hit(clf: LexiconRegisterClassifier) -> None:
    """Mixed-register sample — formal + business markers, distribution
    spans 2 classes and still sums to 1."""
    text = "Báo cáo công ty căn cứ thông tư mới, doanh thu quý 1 đạt mục tiêu."
    result = clf.predict(text)
    total = sum(result.distribution.values())
    assert abs(total - 1.0) < 1e-6
    assert result.score == max(result.distribution.values())
