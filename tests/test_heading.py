"""Tests for nom.text.heading."""

from __future__ import annotations

import pytest

from nom.text.heading import is_heading, merge_tone_only


class TestIsHeading:
    @pytest.mark.parametrize(
        "text",
        [
            "Độc lập - Tự do - Hạnh phúc",
            "ĐƠN XIN NGHỈ VIỆC",
            "GIẤY CHỨNG NHẬN ĐĂNG KÝ KINH DOANH",
            "Kính gửi: Ban Giám đốc Công ty",
            "BIÊN BẢN HỌP HỘI ĐỒNG QUẢN TRỊ",
        ],
    )
    def test_document_furniture(self, text: str) -> None:
        assert is_heading(text)

    @pytest.mark.parametrize(
        "text",
        [
            "hôm nay trời đẹp quá",
            "Tôi rất hạnh phúc khi gặp lại bạn.",
            "Anh ấy là một người bạn tốt!",
            "",
            "   ",
            "123 456",
        ],
    )
    def test_not_furniture(self, text: str) -> None:
        assert not is_heading(text)

    def test_sentence_final_punctuation_disqualifies(self) -> None:
        assert is_heading("Kính gửi Ban Giám đốc")
        assert not is_heading("Kính gửi Ban Giám đốc.")

    def test_long_input_disqualifies(self) -> None:
        long_title = " ".join(["Từ"] * 13)
        assert not is_heading(long_title)

    def test_lowercase_prose_is_not_a_heading(self) -> None:
        assert not is_heading("độc lập tự do hạnh phúc")


class TestMergeToneOnly:
    def test_accepts_tone_edit(self) -> None:
        assert merge_tone_only("Hạnh phục", "hạnh phúc") == "Hạnh phúc"

    def test_restores_title_case(self) -> None:
        got = merge_tone_only("Độc lập - Tự do - Hạnh phục", "độc lập - tự do - hạnh phúc")
        assert got == "Độc lập - Tự do - Hạnh phúc"

    def test_restores_upper_case(self) -> None:
        assert merge_tone_only("ĐƠN XIN NGHĨ VIỆC", "đơn xin nghỉ việc") == "ĐƠN XIN NGHỈ VIỆC"

    def test_rejects_non_tone_edit(self) -> None:
        # `yu` -> `yêu` is a letter-level edit, not a tone edit.
        assert merge_tone_only("Toi yu Vit Nam", "tôi yêu việt nam") == "Toi yu Vit Nam"

    def test_rejects_edits_to_tokens_with_digits(self) -> None:
        assert merge_tone_only("Số: 15/QĐ-UBND", "số: 15/qđ-bnd") == "Số: 15/QĐ-UBND"

    def test_rejects_vowel_modifier_change(self) -> None:
        # `ơ` -> `o` changes the vowel, not the tone, so it must not pass.
        assert merge_tone_only("Cơm", "com") == "Cơm"

    def test_abandons_merge_on_token_count_mismatch(self) -> None:
        assert merge_tone_only("Hạnh phục", "hạnh phúc quá") == "Hạnh phục"

    def test_identical_input_is_unchanged(self) -> None:
        assert merge_tone_only("Hạnh phúc", "hạnh phúc") == "Hạnh phúc"

    def test_preserves_lowercase_tokens(self) -> None:
        assert merge_tone_only("Hà Nội, ngày 15", "hà nội, ngày 15") == "Hà Nội, ngày 15"
