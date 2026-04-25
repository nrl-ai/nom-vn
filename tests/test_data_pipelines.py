"""End-to-end tests against the committed VN data corpora in benchmarks/data/.

Skipped (per-test) when the data folders are absent (e.g. fresh clone
that hasn't run benchmarks/data/_fetch_all.py). Skipped (per-test) when
optional deps are absent (pytesseract for OCR, pdfplumber for PDFs).

These are *integration* tests — they exercise the real nom.text /
nom.chunking / nom.doc.Pipeline / nom.embeddings (where light) paths
against text the user actually staged. They run in seconds because the
fixtures are small (one PDF, a handful of TXT, a handful of PNGs).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "benchmarks" / "data"


# ---------------------------------------------------------------------------
# Markers / skip helpers
# ---------------------------------------------------------------------------


def _have(p: Path) -> bool:
    return p.exists()


def _have_pytesseract() -> bool:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def _have_pdfplumber() -> bool:
    try:
        import pdfplumber  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Wikipedia VN — long-text RAG smoke test through chunking
# ---------------------------------------------------------------------------


WIKI_JSONL = DATA / "wiki_vi" / "articles.jsonl"


@pytest.mark.skipif(not _have(WIKI_JSONL), reason="wiki_vi corpus not staged")
class TestWikipediaVI:
    @pytest.fixture
    def first_article(self) -> dict:
        with WIKI_JSONL.open(encoding="utf-8") as f:
            return json.loads(f.readline())

    def test_first_article_nontrivial(self, first_article: dict) -> None:
        # Sanity: the article is real VN text with diacritics.
        assert "title" in first_article
        assert "extract" in first_article
        assert len(first_article["extract"]) > 500
        # Vietnamese-specific characters present (diacritic markers).
        assert any(c in first_article["extract"] for c in "ếốứờàắệộ")

    def test_chunking_produces_sentence_aligned_chunks(self, first_article: dict) -> None:
        from nom.chunking import smart_chunk

        chunks = smart_chunk(first_article["extract"], max_tokens=256, overlap=32)
        assert len(chunks) >= 2  # long enough to split
        # Each chunk should end with sentence punctuation (chunker is VN-aware).
        end_chars = {c.text[-1] for c in chunks if c.text}
        # At least one common sentence terminator must appear at chunk boundaries.
        assert end_chars & set(".!?…")

    def test_chunk_overlap_preserves_continuity(self, first_article: dict) -> None:
        from nom.chunking import smart_chunk

        chunks = smart_chunk(first_article["extract"], max_tokens=256, overlap=64)
        # If overlap > 0 and we have ≥2 chunks, the join should reconstruct
        # MORE characters than the source (because of the overlap region).
        joined = sum(len(c.text) for c in chunks)
        if len(chunks) >= 2:
            assert joined >= len(first_article["extract"])


# ---------------------------------------------------------------------------
# Truyện Kiều — pure text Pipeline smoke test
# ---------------------------------------------------------------------------


KIEU = DATA / "wikisource_vi" / "tua_truyen_kieu.txt"


@pytest.mark.skipif(not _have(KIEU), reason="wikisource_vi corpus not staged")
class TestTruyenKieu:
    def test_pipeline_extracts_text(self) -> None:
        from nom.doc import Context, Load, Normalize, Parse

        ctx = Context(source=str(KIEU))
        Load().run(ctx)
        Parse().run(ctx)
        Normalize().run(ctx)
        assert ctx.text
        assert len(ctx.text) > 200
        # The text should still contain Truyện Kiều markers after normalize.
        assert "Kiều" in ctx.text or "kiều" in ctx.text.lower()


# ---------------------------------------------------------------------------
# UDHR — PDF parse round-trip
# ---------------------------------------------------------------------------


UDHR_PDF = DATA / "udhr_vi" / "udhr_vie.pdf"
UDHR_TXT = DATA / "udhr_vi" / "udhr_vi.txt"


def _pdf_has_unicode(path: Path) -> bool:
    """Return True if a PDF's first page yields real Unicode (not glyph IDs).

    Font-subset PDFs without a ToUnicode CMap return things like
    ``(cid:55)(cid:88)…`` from pdfplumber. The UDHR Vietnamese PDF on
    unicode.org is one such file. There's no fix at the parser level —
    the PDF lacks the data needed to recover the original characters.
    OCR is the only path. We skip the text-path test for those.
    """
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            head = (pdf.pages[0].extract_text() or "")[:300]
    except Exception:
        return False
    return "(cid:" not in head


@pytest.mark.skipif(
    not (_have(UDHR_PDF) and _have_pdfplumber()),
    reason="udhr_vi PDF or pdfplumber not available",
)
class TestUDHRPDF:
    def test_pdf_text_extracted(self) -> None:
        if not _pdf_has_unicode(UDHR_PDF):
            pytest.skip(
                "PDF uses font-subset glyph IDs without a ToUnicode CMap "
                "(real-world gotcha — needs OCR pipeline, not text extraction)."
            )
        from nom.doc import Context, Load, Normalize, Parse

        ctx = Context(source=str(UDHR_PDF))
        Load().run(ctx)
        Parse().run(ctx)
        Normalize().run(ctx)
        assert len(ctx.text) > 2_000
        assert any(c in ctx.text for c in "ếốứờàắệộ")

    @pytest.mark.skipif(not _have(UDHR_TXT), reason="udhr_vi.txt missing")
    def test_pdf_overlaps_with_committed_txt(self) -> None:
        if not _pdf_has_unicode(UDHR_PDF):
            pytest.skip("PDF uses cid: glyph IDs — see TestUDHRPDF docstring.")
        from nom.doc import Context, Load, Normalize, Parse

        ctx = Context(source=str(UDHR_PDF))
        Load().run(ctx)
        Parse().run(ctx)
        Normalize().run(ctx)
        pdf_text = ctx.text.lower()
        txt = UDHR_TXT.read_text(encoding="utf-8").lower()
        for phrase in ("nhân quyền", "tự do"):
            assert phrase in pdf_text, f"missing in PDF: {phrase}"
            assert phrase in txt, f"missing in committed txt: {phrase}"


# ---------------------------------------------------------------------------
# Synthetic OCR PNGs — exact-match against committed ground truth
# ---------------------------------------------------------------------------


OCR_DIR = DATA / "synthetic_ocr_vi"
OCR_GT = OCR_DIR / "ground_truth.jsonl"


@pytest.mark.skipif(
    not (_have(OCR_GT) and _have_pytesseract()),
    reason="synthetic_ocr_vi or tesseract not available",
)
class TestSyntheticOCR:
    @pytest.fixture
    def ground_truth(self) -> list[dict]:
        with OCR_GT.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_clean_first_image_exact_match(self, ground_truth: list[dict]) -> None:
        """OCR'ing the first clean image should reproduce its ground truth."""
        from nom.doc import OCR, Context, Load, Normalize, Parse

        gt = ground_truth[0]
        path = OCR_DIR / gt["clean"]
        if not path.is_file():
            pytest.skip(f"missing image {path}")
        # OCR needs the language data dir set; auto-detect like the CLI does.
        if "TESSDATA_PREFIX" not in os.environ:
            tesseract_bin = shutil.which("tesseract")
            if tesseract_bin:
                candidate = Path(tesseract_bin).parent.parent / "share" / "tessdata"
                if (candidate / "vie.traineddata").is_file():
                    os.environ["TESSDATA_PREFIX"] = str(candidate)
        ctx = Context(source=str(path))
        Load().run(ctx)
        Parse().run(ctx)
        OCR().run(ctx)
        Normalize().run(ctx)
        # OCR can introduce trailing whitespace; compare stripped.
        assert ctx.text.strip() == gt["text"].strip()

    def test_clean_first_three_images_high_match_rate(self, ground_truth: list[dict]) -> None:
        """Across the first three clean images, we expect near-perfect VN OCR."""
        from nom.doc import OCR, Context, Load, Normalize, Parse

        if "TESSDATA_PREFIX" not in os.environ:
            tesseract_bin = shutil.which("tesseract")
            if tesseract_bin:
                candidate = Path(tesseract_bin).parent.parent / "share" / "tessdata"
                if (candidate / "vie.traineddata").is_file():
                    os.environ["TESSDATA_PREFIX"] = str(candidate)
        n_match = 0
        n_tested = 0
        for gt in ground_truth[:3]:
            path = OCR_DIR / gt["clean"]
            if not path.is_file():
                continue
            ctx = Context(source=str(path))
            Load().run(ctx)
            Parse().run(ctx)
            OCR().run(ctx)
            Normalize().run(ctx)
            n_tested += 1
            if ctx.text.strip() == gt["text"].strip():
                n_match += 1
        assert n_tested >= 1
        # Allow at most one miss out of three on clean fonts.
        assert n_match >= max(1, n_tested - 1)
