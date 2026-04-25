"""Tests for nom.chunking — pure-Python VN-aware document chunking."""

from __future__ import annotations

import itertools

import pytest

from nom.chunking import BoundaryMode, Chunk, paragraph_chunk, sentence_chunk, smart_chunk

# ---------------------------------------------------------------------------
# Fixtures — realistic VN text at multiple sizes
# ---------------------------------------------------------------------------

SHORT_TEXT = "Hợp đồng số HD-001. Bên A: Cty Hồng Hà. Bên B: Bà Nguyễn Thị Hương."

MEDIUM_TEXT = """\
Hợp đồng số 02/HĐ/2025 được lập ngày 14 tháng 3 năm 2025.

Bên A: Công ty Cổ phần Hồng Hà, mã số thuế 0123456789.
Bên B: Bà Nguyễn Thị Hương, sinh năm 1990, địa chỉ tại Hà Nội.

Tổng giá trị hợp đồng là một tỷ năm trăm triệu đồng chẵn.
Thời hạn thực hiện sáu tháng kể từ ngày ký kết hợp đồng."""

LONG_TEXT = "\n\n".join([MEDIUM_TEXT] * 10)


# ---------------------------------------------------------------------------
# Validation — clear errors on bad inputs
# ---------------------------------------------------------------------------


class TestValidation:
    def test_max_tokens_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match=r"max_tokens"):
            smart_chunk("hello", max_tokens=0)

    def test_overlap_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match=r"overlap"):
            smart_chunk("hello", max_tokens=100, overlap=-1)

    def test_overlap_must_be_less_than_max_tokens(self) -> None:
        with pytest.raises(ValueError, match=r"overlap"):
            smart_chunk("hello", max_tokens=10, overlap=10)
        with pytest.raises(ValueError, match=r"overlap"):
            smart_chunk("hello", max_tokens=10, overlap=20)

    def test_empty_text_yields_empty_list(self) -> None:
        assert smart_chunk("") == []
        assert sentence_chunk("") == []
        assert paragraph_chunk("") == []

    def test_invalid_boundary_string_raises(self) -> None:
        with pytest.raises(ValueError, match=r"bogus"):
            smart_chunk("hello", boundary="bogus")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Sentence chunking — the default path
# ---------------------------------------------------------------------------


class TestSentenceChunk:
    def test_short_text_one_chunk(self) -> None:
        chunks = sentence_chunk(SHORT_TEXT, max_tokens=512, overlap=0)
        assert len(chunks) == 1
        assert "Hợp đồng" in chunks[0].text

    def test_token_count_within_max_for_non_truncated(self) -> None:
        chunks = sentence_chunk(MEDIUM_TEXT, max_tokens=15, overlap=0)
        for c in chunks:
            if c.metadata.get("truncated"):
                # Truncated (oversized-sentence fallback) chunks may exceed
                # max_tokens because character-window estimation is approximate.
                # The metadata flag is the contract.
                continue
            assert c.n_tokens <= 15, f"chunk exceeds max: {c.n_tokens} tokens"

    def test_offsets_are_in_source(self) -> None:
        chunks = sentence_chunk(MEDIUM_TEXT, max_tokens=20, overlap=0)
        for c in chunks:
            # The recorded slice should contain the chunk's text (modulo edges)
            slice_text = MEDIUM_TEXT[c.start : c.end]
            assert c.text.strip() in slice_text or slice_text.strip() in c.text

    def test_chunks_cover_in_order(self) -> None:
        chunks = sentence_chunk(MEDIUM_TEXT, max_tokens=20, overlap=0)
        for prev, cur in itertools.pairwise(chunks):
            assert prev.start <= cur.start

    def test_overlap_increases_chunk_count(self) -> None:
        no_overlap = sentence_chunk(LONG_TEXT, max_tokens=30, overlap=0)
        with_overlap = sentence_chunk(LONG_TEXT, max_tokens=30, overlap=8)
        # Overlap shouldn't decrease chunk count (often increases it).
        assert len(with_overlap) >= len(no_overlap)

    def test_metadata_marks_boundary(self) -> None:
        chunks = sentence_chunk(MEDIUM_TEXT, max_tokens=512, overlap=0)
        assert chunks[0].metadata["boundary"] in ("sentence", "character")

    def test_returns_chunk_dataclass(self) -> None:
        chunks = sentence_chunk(SHORT_TEXT, max_tokens=512, overlap=0)
        assert isinstance(chunks[0], Chunk)
        # Frozen dataclass — assignment raises FrozenInstanceError (subclass of AttributeError)
        with pytest.raises((AttributeError, TypeError)):
            chunks[0].text = "x"  # type: ignore[misc]

    def test_long_sentence_falls_back_to_character_chunking(self) -> None:
        # Force a single sentence longer than max_tokens.
        long_sentence = ("Hợp đồng " * 100).rstrip() + "."
        chunks = sentence_chunk(long_sentence, max_tokens=10, overlap=2)
        assert len(chunks) > 1
        # At least one chunk should be character-mode + truncated flagged
        truncated = [c for c in chunks if c.metadata.get("truncated")]
        assert truncated


# ---------------------------------------------------------------------------
# Paragraph chunking
# ---------------------------------------------------------------------------


class TestParagraphChunk:
    def test_respects_paragraph_boundaries(self) -> None:
        chunks = paragraph_chunk(MEDIUM_TEXT, max_tokens=512, overlap=0)
        # Every chunk should be a complete paragraph (no mid-paragraph splits).
        # Verify by checking each chunk doesn't contain '\n\n' inside its text
        # except at the last position.
        for c in chunks:
            inner = c.text.strip()
            assert "\n\n" not in inner

    def test_oversize_paragraph_falls_back_to_sentence(self) -> None:
        # 6-paragraph long doc; force a paragraph to exceed max_tokens.
        big_para = " ".join(["Câu này dài và lặp lại."] * 50)
        chunks = paragraph_chunk(big_para, max_tokens=15, overlap=0)
        assert any("paragraph→sentence" in c.metadata.get("boundary", "") for c in chunks)


# ---------------------------------------------------------------------------
# Character chunking — the last-resort path
# ---------------------------------------------------------------------------


class TestCharacterChunk:
    def test_basic(self) -> None:
        text = "Lorem ipsum " * 50
        chunks = smart_chunk(text, max_tokens=10, overlap=2, boundary=BoundaryMode.CHARACTER)
        assert len(chunks) > 1
        for c in chunks:
            assert c.metadata["boundary"] == "character"

    def test_offsets_walk_forward(self) -> None:
        text = "Lorem " * 200
        chunks = smart_chunk(text, max_tokens=20, overlap=0, boundary="character")
        for prev, cur in itertools.pairwise(chunks):
            assert cur.start >= prev.start


# ---------------------------------------------------------------------------
# smart_chunk dispatches correctly
# ---------------------------------------------------------------------------


class TestSmartChunkDispatch:
    def test_default_is_sentence(self) -> None:
        chunks = smart_chunk(SHORT_TEXT, max_tokens=512, overlap=0)
        assert chunks[0].metadata["boundary"] in ("sentence", "character")

    def test_string_mode(self) -> None:
        chunks = smart_chunk(MEDIUM_TEXT, max_tokens=512, overlap=0, boundary="paragraph")
        assert all("paragraph" in c.metadata.get("boundary", "") for c in chunks)

    def test_enum_mode(self) -> None:
        chunks = smart_chunk(MEDIUM_TEXT, max_tokens=10, overlap=0, boundary=BoundaryMode.CHARACTER)
        assert all(c.metadata["boundary"] == "character" for c in chunks)


# ---------------------------------------------------------------------------
# Chunk dataclass invariants
# ---------------------------------------------------------------------------


class TestChunkClass:
    def test_len_returns_text_length(self) -> None:
        c = Chunk(text="hello", start=0, end=5, n_tokens=1)
        assert len(c) == 5

    def test_metadata_default_is_independent(self) -> None:
        # Frozen dataclass with default_factory — different instances should
        # NOT share the same metadata dict.
        a = Chunk(text="a", start=0, end=1, n_tokens=1)
        b = Chunk(text="b", start=0, end=1, n_tokens=1)
        a.metadata["x"] = 1
        assert "x" not in b.metadata

    def test_frozen(self) -> None:
        c = Chunk(text="x", start=0, end=1, n_tokens=1)
        with pytest.raises((AttributeError, TypeError)):
            c.text = "y"  # type: ignore[misc]
