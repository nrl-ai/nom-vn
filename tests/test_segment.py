"""Tests for nom.text.segment — pure-Python tokenization (no third-party deps).

Should run on a stock Python install. No `pytest.importorskip` needed.
"""

from __future__ import annotations

import pytest

from nom.text import sent_tokenize, text_normalize, word_tokenize


class TestWordTokenize:
    def test_empty(self) -> None:
        assert word_tokenize("") == []
        assert word_tokenize("", fmt="text") == ""

    def test_single_word(self) -> None:
        assert word_tokenize("xin") == ["xin"]

    def test_compound_word_kept_together(self) -> None:
        # "Hợp đồng" is in the compound table — should merge
        result = word_tokenize("Hợp đồng số 02")
        assert "Hợp đồng" in result
        assert result == ["Hợp đồng", "số", "02"]

    def test_long_compound_preferred(self) -> None:
        # "thành phố hồ chí minh" is a 4-token compound
        result = word_tokenize("Tôi sống ở thành phố Hồ Chí Minh")
        joined = "/".join(result)
        assert "thành phố Hồ Chí Minh" in joined or "thành phố hồ chí minh" in joined.lower()

    def test_text_format_uses_underscore(self) -> None:
        out = word_tokenize("Hợp đồng số 02", fmt="text")
        assert isinstance(out, str)
        assert "Hợp_đồng" in out

    def test_punctuation_split_out(self) -> None:
        result = word_tokenize("Hợp đồng, được lập")
        assert "," in result

    def test_no_compound_passes_through(self) -> None:
        result = word_tokenize("xin chào tôi đến")
        # "xin chào" IS a compound; "tôi đến" is not — they should split
        assert "tôi" in result
        assert "đến" in result

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match=r"fmt"):
            word_tokenize("text", fmt="bogus")

    def test_case_preserved_in_output(self) -> None:
        # Compound table is lowercase; lookup is case-insensitive but output keeps original
        result = word_tokenize("Hợp Đồng số 02")
        # "Hợp Đồng" (with capital Đ) should still be merged
        assert any("Hợp" in t and "Đồng" in t for t in result)

    def test_preserves_unknown_tokens(self) -> None:
        # Made-up word not in any table — passes through
        result = word_tokenize("zxqwerty là một từ lạ")
        assert "zxqwerty" in result


class TestSentTokenize:
    def test_empty(self) -> None:
        assert sent_tokenize("") == []

    def test_simple_split(self) -> None:
        sents = sent_tokenize("Hôm nay trời mưa to. Anh có cần ô không?")
        assert len(sents) == 2
        assert sents[0].endswith(".")
        assert sents[1].endswith("?")

    def test_single_sentence(self) -> None:
        assert sent_tokenize("Một câu thôi") == ["Một câu thôi"]

    def test_multiple_terminators(self) -> None:
        sents = sent_tokenize("Câu một. Câu hai! Câu ba? Câu bốn.")
        assert len(sents) == 4

    def test_abbreviation_does_not_split(self) -> None:
        # "TP." is a recognized abbreviation — should NOT split
        sents = sent_tokenize("Tôi sống ở TP. Hồ Chí Minh và làm việc ở Hà Nội.")
        # Should be one or two sentences depending on capitalization heuristic,
        # but NOT three (no split at "TP.").
        for s in sents:
            assert not s.endswith("TP.") or "Hồ Chí Minh" in s or len(sents) == 1

    def test_preserves_terminal_punctuation(self) -> None:
        sents = sent_tokenize("Một. Hai!")
        for s in sents:
            assert s[-1] in ".!?…"


class TestTextNormalize:
    def test_empty(self) -> None:
        assert text_normalize("") == ""

    def test_idempotent(self) -> None:
        text = "Hợp đồng được lập ngày 14, tháng 3."
        assert text_normalize(text_normalize(text)) == text_normalize(text)

    def test_collapses_multi_whitespace(self) -> None:
        result = text_normalize("Hợp  đồng    được   lập")
        assert "  " not in result

    def test_removes_space_before_punctuation(self) -> None:
        result = text_normalize("Hợp đồng , được lập .")
        assert " ," not in result
        assert " ." not in result
        assert "," in result
        assert "." in result

    def test_adds_space_after_punctuation(self) -> None:
        result = text_normalize("Một,Hai,Ba")
        # After "," there should be a space before each next word.
        assert ", H" in result or ", h" in result

    def test_strips_leading_trailing(self) -> None:
        assert text_normalize("   xin chào   ") == "xin chào"

    def test_applies_nfc(self) -> None:
        # decomposed "co" + combining hook → "cỏ"
        result = text_normalize("co" + "̉")
        assert result == "cỏ"

    def test_preserves_vn_decimal_comma(self) -> None:
        """VN uses ',' as decimal separator. text_normalize must NOT
        add a space inside '5,66%' or it breaks RAG indexing
        (the chunker re-splits on the synthetic space and citations
        come back as '5, 66%')."""
        assert text_normalize("GDP tăng 5,66% so với") == "GDP tăng 5,66% so với"
        assert text_normalize("102,5 tỷ USD") == "102,5 tỷ USD"

    def test_preserves_vn_thousand_separator_dot(self) -> None:
        """VN uses '.' as thousand separator. '1.500.000.000' must stay
        intact, not become '1. 500. 000. 000'."""
        assert text_normalize("Tổng 1.500.000.000 đồng") == "Tổng 1.500.000.000 đồng"
        # Mixed: thousand-separator dots + sentence-end dot
        assert text_normalize("Đạt 1.500.000.Số tiếp theo.") == "Đạt 1.500.000. Số tiếp theo."
