"""Tests for ``nom.platform.privacy`` — VN regex PII + redactor policies."""

from __future__ import annotations

import pytest

from nom.platform import (
    MaskRedactor,
    PIIDetector,
    PIISpan,
    Redactor,
    RegexPIIDetector,
)


def test_regex_detector_satisfies_protocol() -> None:
    assert isinstance(RegexPIIDetector(), PIIDetector)


def test_mask_redactor_satisfies_protocol() -> None:
    assert isinstance(MaskRedactor(), Redactor)


# ---- detection ------------------------------------------------------


def test_detects_email() -> None:
    spans = RegexPIIDetector().detect("Liên hệ user@vcb.vn để biết thêm.")
    kinds = {s.kind for s in spans}
    assert "email" in kinds


def test_detects_vn_mobile() -> None:
    spans = RegexPIIDetector().detect("SĐT: 0912345678 hoặc +84987654321.")
    phones = [s for s in spans if s.kind == "phone_vn"]
    assert len(phones) == 2


def test_detects_cccd_12_digits() -> None:
    spans = RegexPIIDetector().detect("CCCD 001234567890 cấp ngày 2024.")
    assert any(s.kind == "cccd" and s.value == "001234567890" for s in spans)


def test_detects_cmnd_9_digits_when_no_collision() -> None:
    spans = RegexPIIDetector().detect("CMND số 123456789 cũ.")
    assert any(s.kind == "cmnd" and s.value == "123456789" for s in spans)


def test_detects_mst_with_branch() -> None:
    spans = RegexPIIDetector().detect("MST: 0312345678-001 chi nhánh 1.")
    assert any(s.kind == "mst" for s in spans)


def test_spans_non_overlapping_and_sorted() -> None:
    from itertools import pairwise

    text = "user@a.vn 0912345678 001234567890"
    spans = RegexPIIDetector().detect(text)
    for prev, curr in pairwise(spans):
        assert prev.end <= curr.start
    assert list(spans) == sorted(spans, key=lambda s: s.start)


def test_priority_cccd_over_stk_on_overlap() -> None:
    # 12 digits = both CCCD pattern and STK pattern would match;
    # CCCD has higher priority.
    spans = RegexPIIDetector().detect("Số 001234567890")
    kinds = {s.kind for s in spans}
    assert "cccd" in kinds
    assert "stk_vn" not in kinds


# ---- redaction ------------------------------------------------------


def test_mask_policy_replaces_with_kind_placeholder() -> None:
    detector = RegexPIIDetector()
    redactor = MaskRedactor()
    text = "Email tôi: alice@bank.vn"
    spans = detector.detect(text)
    out = redactor.redact(text, spans, policy="mask")
    assert "alice@bank.vn" not in out
    assert "[EMAIL]" in out


def test_drop_policy_removes_span() -> None:
    redactor = MaskRedactor()
    text = "Số CCCD 001234567890."
    spans = (PIISpan(8, 20, "cccd", "001234567890"),)
    out = redactor.redact(text, spans, policy="drop")
    assert "001234567890" not in out
    assert out == "Số CCCD ."


def test_hash_policy_is_deterministic() -> None:
    redactor = MaskRedactor(hash_secret=b"secret")
    spans = (PIISpan(0, 13, "email", "user@vcb.vn"),)
    out1 = redactor.redact("user@vcb.vn  hello", spans, policy="hash")
    out2 = redactor.redact("user@vcb.vn  hello", spans, policy="hash")
    assert out1 == out2
    assert "user@vcb.vn" not in out1
    assert "[email:" in out1


def test_hash_policy_differs_per_secret() -> None:
    a = MaskRedactor(hash_secret=b"a-key")
    b = MaskRedactor(hash_secret=b"b-key")
    spans = (PIISpan(0, 11, "email", "u@example.vn"),)
    text = "u@example.vn"
    assert a.redact(text, spans, policy="hash") != b.redact(text, spans, policy="hash")


def test_unknown_policy_raises() -> None:
    redactor = MaskRedactor()
    spans = (PIISpan(0, 1, "x", "x"),)
    with pytest.raises(ValueError, match="unknown redact policy"):
        redactor.redact("x", spans, policy="bogus")


def test_redact_no_spans_returns_input_unchanged() -> None:
    redactor = MaskRedactor()
    assert redactor.redact("hello", (), policy="mask") == "hello"


def test_redact_preserves_text_outside_spans() -> None:
    redactor = MaskRedactor()
    text = "Tên: Nguyễn Văn A — Email: a@b.vn — Tuổi: 30"
    detector = RegexPIIDetector()
    out = redactor.redact(text, detector.detect(text), policy="mask")
    assert "Tên: Nguyễn Văn A" in out
    assert "Tuổi: 30" in out
    assert "a@b.vn" not in out
