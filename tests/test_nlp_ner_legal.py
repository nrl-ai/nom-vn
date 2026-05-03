"""Tests for nom.nlp.ner_legal — VN legal-domain regex extensions."""

from __future__ import annotations

import pytest

from nom.nlp.ner import RegexNERModel
from nom.nlp.ner_legal import legal_ner_patterns


@pytest.fixture
def ner() -> RegexNERModel:
    return RegexNERModel(extra_patterns=legal_ner_patterns())


def labels_in(text: str, ner: RegexNERModel) -> set[str]:
    return {span.label for span in ner.tag(text)}


def test_law_ref_full_form(ner: RegexNERModel) -> None:
    text = "Theo Nghị định 134/2025/NĐ-CP, các bên cam kết thực hiện."
    spans = ner.tag(text)
    law_refs = [s for s in spans if s.label == "LAW_REF"]
    assert len(law_refs) >= 1
    assert any("134/2025" in s.text for s in law_refs)


def test_law_ref_with_qh_suffix(ner: RegexNERModel) -> None:
    text = "Căn cứ Luật số 50/2024/QH15 ban hành năm 2024."
    spans = ner.tag(text)
    assert any(s.label == "LAW_REF" and "QH15" in s.text for s in spans)


def test_article_reference(ner: RegexNERModel) -> None:
    text = "Theo Điều 5 và Khoản 2 của hợp đồng, bên A có quyền…"
    spans = ner.tag(text)
    refs = [s for s in spans if s.label == "LAW_REF"]
    # Should pick up at least Điều 5 and Khoản 2
    assert len(refs) >= 2


def test_id_number_12_digits(ner: RegexNERModel) -> None:
    text = "Số định danh cá nhân: 012345678901."
    assert "ID_VN" in labels_in(text, ner)


def test_id_number_9_digits(ner: RegexNERModel) -> None:
    text = "CMND số 012345678 cấp tại Hà Nội."
    assert "ID_VN" in labels_in(text, ner)


def test_phone_vn_zero_prefix(ner: RegexNERModel) -> None:
    text = "Liên hệ 0912 345 678 hoặc email."
    assert "PHONE_VN" in labels_in(text, ner)


def test_phone_vn_country_code(ner: RegexNERModel) -> None:
    text = "Hotline: +84 24 1234 5678."
    assert "PHONE_VN" in labels_in(text, ner)


def test_combined_legal_doc(ner: RegexNERModel) -> None:
    """Spot-check a paragraph that combines several legal entity types."""
    text = (
        "Theo Nghị định 13/2023/NĐ-CP và Điều 5 Luật An ninh mạng, "
        "ông Nguyễn Văn A (CMND 012345678, điện thoại 0912 345 678) "
        "đồng ý thanh toán 1.500.000 VND vào ngày 14/3/2025."
    )
    labels = labels_in(text, ner)
    # Legal extensions
    assert "LAW_REF" in labels
    assert "ID_VN" in labels
    assert "PHONE_VN" in labels
    # Standard regex patterns must still fire alongside the extensions
    assert "MONEY" in labels
    assert "DATE" in labels


def test_no_false_positive_on_invoice_number(ner: RegexNERModel) -> None:
    """An invoice number shouldn't be ID_VN unless it's exactly 9/12 digits.

    20-digit transaction IDs and 6-digit codes are common in receipts —
    must not get tagged.
    """
    text = "Mã hóa đơn 12345678901234567890 và mã đơn 123456 không phải ID."
    spans = ner.tag(text)
    id_spans = [s for s in spans if s.label == "ID_VN"]
    assert id_spans == []
