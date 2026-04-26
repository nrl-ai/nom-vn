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


class _FakeDiacriticLLM:
    """Records prompts; returns canned VN-restored answers per call."""

    name = "fake-diacritic-llm"

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, schema: object = None, max_tokens: int = 2048) -> str:
        self.prompts.append(prompt)
        return self.response


class TestFixDiacriticsLLM:
    def test_llm_path_replaces_rule_path(self) -> None:
        llm = _FakeDiacriticLLM(response="Hợp đồng số 02 ngày 14/3/2025.")
        out = fix_diacritics("Hop dong so 02 ngay 14/3/2025.", llm=llm)
        assert out == "Hợp đồng số 02 ngày 14/3/2025."
        # The VN-prompt template should have appeared in the LLM call.
        assert "Khôi phục dấu" in llm.prompts[0]
        assert "Hop dong so 02 ngay 14/3/2025." in llm.prompts[0]

    def test_llm_strips_think_tag(self) -> None:
        # Models like qwen3 emit <think>reasoning</think> before the answer.
        # Our defensive trim must strip it.
        llm = _FakeDiacriticLLM(
            response="<think>I need to add tone marks</think>\nHợp đồng",
        )
        out = fix_diacritics("Hop dong", llm=llm)
        assert out == "Hợp đồng"

    def test_llm_strips_label_echo(self) -> None:
        # Models sometimes echo the label before the answer.
        llm = _FakeDiacriticLLM(response="Văn bản đã khôi phục dấu:\nHợp đồng")
        out = fix_diacritics("Hop dong", llm=llm)
        assert out == "Hợp đồng"

    def test_llm_strips_code_fence(self) -> None:
        llm = _FakeDiacriticLLM(response="```\nHợp đồng\n```")
        out = fix_diacritics("Hop dong", llm=llm)
        assert out == "Hợp đồng"

    def test_llm_path_preserves_paragraph_breaks(self) -> None:
        # Multi-paragraph input → one LLM call per non-blank chunk;
        # blank-line separators preserved.
        llm = _FakeDiacriticLLM(response="đoạn văn")
        text = "doan van\n\ndoan khac"
        out = fix_diacritics(text, llm=llm)
        # We expect "đoạn văn" returned for both paragraphs (fake llm
        # doesn't differentiate); the blank line is preserved.
        assert "\n\n" in out
        # Two paragraph-shaped LLM calls, blank-line in-between is not sent.
        assert len(llm.prompts) == 2

    def test_llm_path_empty_input_short_circuits(self) -> None:
        llm = _FakeDiacriticLLM(response="should-not-appear")
        assert fix_diacritics("", llm=llm) == ""
        assert llm.prompts == []  # never called
