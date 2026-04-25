"""Tests for nom.text.normalize."""

from __future__ import annotations

import unicodedata

from nom.text import (
    fix_diacritics,
    has_diacritics,
    is_vietnamese,
    normalize,
    strip_diacritics,
)


class TestNormalize:
    def test_nfc_compose(self) -> None:
        # "co" + combining-hook-above → "cỏ" composed
        decomposed = "co" + "̉"
        assert decomposed != "cỏ"  # different bytes pre-normalize
        assert normalize(decomposed) == "cỏ"

    def test_idempotent(self) -> None:
        text = "Hợp đồng số 02/HĐ/2025"
        assert normalize(normalize(text)) == normalize(text)

    def test_passes_through_ascii(self) -> None:
        assert normalize("hello world") == "hello world"

    def test_empty(self) -> None:
        assert normalize("") == ""


class TestStripDiacritics:
    def test_strips_tone_marks(self) -> None:
        assert strip_diacritics("Hợp đồng số 02/HĐ/2025") == "Hop dong so 02/HD/2025"

    def test_strips_d_with_stroke(self) -> None:
        assert strip_diacritics("đồng") == "dong"
        assert strip_diacritics("Đại Việt") == "Dai Viet"

    def test_idempotent_on_ascii(self) -> None:
        assert strip_diacritics("contract") == "contract"

    def test_preserves_punctuation_and_digits(self) -> None:
        assert strip_diacritics("HĐ-2025-002") == "HD-2025-002"


class TestHasDiacritics:
    def test_true_for_diacritic_text(self) -> None:
        assert has_diacritics("tiếng Việt") is True

    def test_true_for_d_with_stroke(self) -> None:
        assert has_diacritics("đồng") is True

    def test_false_for_ascii(self) -> None:
        assert has_diacritics("hello") is False
        assert has_diacritics("Hop dong") is False

    def test_false_for_empty(self) -> None:
        assert has_diacritics("") is False


class TestIsVietnamese:
    def test_diacritic_text(self) -> None:
        assert is_vietnamese("Hợp đồng số 02/HĐ/2025") is True

    def test_diacritic_stripped_text(self) -> None:
        # High vowel ratio Vietnamese should still be detected
        assert is_vietnamese("Hop dong nay duoc lap") is True

    def test_english_returns_false(self) -> None:
        assert is_vietnamese("This is an English sentence") is False

    def test_too_short(self) -> None:
        assert is_vietnamese("hi") is False
        assert is_vietnamese("") is False


class TestFixDiacritics:
    def test_restores_common_business_words(self) -> None:
        result = fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3")
        # We don't assert exact perfect output (table is small),
        # but key tokens should be restored.
        assert "Hợp" in result
        assert "đồng" in result
        assert "ngày" in result
        assert "tháng" in result

    def test_preserves_capitalization(self) -> None:
        result = fix_diacritics("Hop dong")
        assert result.startswith("Hợp")  # capitalized

    def test_preserves_punctuation_and_numbers(self) -> None:
        result = fix_diacritics("Hop dong 02/HD/2025")
        assert "02/HD/2025" in result

    def test_unknown_words_pass_through(self) -> None:
        # Made-up word not in table should be unchanged
        result = fix_diacritics("xyzunknowntoken hop dong")
        assert "xyzunknowntoken" in result

    def test_empty(self) -> None:
        assert fix_diacritics("") == ""

    def test_output_is_nfc(self) -> None:
        result = fix_diacritics("Hop dong nay duoc lap")
        assert unicodedata.is_normalized("NFC", result)
