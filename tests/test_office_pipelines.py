"""Per-format integration tests for the Office parsers.

Drives ``nom.doc.Parse`` against the synthetic fixtures in
``benchmarks/data/office_vi/`` (regenerable via ``_generate.py``) and
verifies the structural extraction matches the committed
``ground_truth.json`` manifest.

These are intentionally **integration** tests — they import the real
``python-docx`` / ``openpyxl`` / ``python-pptx`` deps and exercise the
end-to-end Parse path. They're skipped when the optional dep isn't
installed, so a minimal ``pip install nom-vn`` doesn't fail CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "benchmarks" / "data" / "office_vi"
GT_PATH = DIR / "ground_truth.json"


def _have(*mods: str) -> bool:
    for m in mods:
        try:
            __import__(m)
        except ImportError:
            return False
    return True


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    # Auto-generate if missing — works on a fresh clone with the
    # optional Office deps installed.
    if not GT_PATH.exists() and _have("docx", "openpyxl", "pptx"):
        subprocess.check_call(
            [sys.executable, str(DIR / "_generate.py")],
            cwd=REPO,
        )
    if not GT_PATH.exists():
        pytest.skip("office_vi fixtures not generated and Office deps missing")
    return json.loads(GT_PATH.read_text(encoding="utf-8"))


def _parse(path: Path) -> dict:
    """Run Load → Parse on a fixture, return ctx as a small dict."""
    from nom.doc import Context, Load, Parse

    ctx = Context(source=str(path))
    Load().run(ctx)
    Parse().run(ctx)
    return {"fmt": ctx.fmt, "pages": ctx.pages_text or [], "text": ctx.text or ""}


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have("docx"), reason="python-docx not installed")
class TestDocxFixture:
    def test_format_detected(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["docx"]["file"])
        assert out["fmt"] == "docx"

    def test_paragraphs_and_table_rows_extracted(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["docx"]["file"])
        # Paragraph + table-row count is at least the manifest's lower bound.
        assert len(out["pages"]) >= ground_truth["docx"]["expected_min_pages"]
        # Every distinctive fragment appears somewhere.
        joined = "\n".join(out["pages"])
        for fragment in ground_truth["docx"]["expected_paragraphs_contain"]:
            assert fragment in joined, f"missing fragment: {fragment!r}"

    def test_table_rows_use_pipe_separator(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["docx"]["file"])
        # Our extractor emits `cell | cell | cell` for table rows so the
        # viewer can render them as a grid. At least one such row must
        # appear (the contract has a 3-column value table).
        assert any(
            " | " in p and p.count(" | ") >= 2 for p in out["pages"]
        ), "no pipe-separated table row found in DOCX output"


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have("openpyxl"), reason="openpyxl not installed")
class TestXlsxFixture:
    def test_format_detected(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["xlsx"]["file"])
        assert out["fmt"] == "xlsx"

    def test_one_page_per_sheet(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["xlsx"]["file"])
        assert len(out["pages"]) == len(ground_truth["xlsx"]["expected_sheets"])

    def test_sheets_have_correct_names(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["xlsx"]["file"])
        # Each page begins with `# <SheetName>`.
        for page, expected_name in zip(
            out["pages"], ground_truth["xlsx"]["expected_sheets"], strict=False
        ):
            first_line = page.split("\n", 1)[0]
            assert (
                first_line == f"# {expected_name}"
            ), f"sheet header mismatch: got {first_line!r}, want '# {expected_name}'"

    def test_data_cells_present(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["xlsx"]["file"])
        joined = "\n".join(out["pages"])
        for fragment in ground_truth["xlsx"]["expected_text_contains"]:
            assert fragment in joined, f"missing cell value: {fragment!r}"


# ---------------------------------------------------------------------------
# PPTX
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have("pptx"), reason="python-pptx not installed")
class TestPptxFixture:
    def test_format_detected(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["pptx"]["file"])
        assert out["fmt"] == "pptx"

    def test_one_page_per_slide(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["pptx"]["file"])
        assert len(out["pages"]) == ground_truth["pptx"]["expected_n_slides"]

    def test_slide_titles_first_line_of_page(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["pptx"]["file"])
        for page, expected_title in zip(
            out["pages"], ground_truth["pptx"]["expected_titles"], strict=False
        ):
            first_line = page.split("\n", 1)[0]
            assert (
                first_line == expected_title
            ), f"slide title mismatch: got {first_line!r}, want {expected_title!r}"

    def test_speaker_notes_extracted(self, ground_truth: dict) -> None:
        out = _parse(DIR / ground_truth["pptx"]["file"])
        joined = "\n".join(out["pages"])
        # Notes are tagged with `_notes:` prefix in the parser output.
        assert "_notes:" in joined, "no speaker notes found in PPTX output"
        for fragment in ground_truth["pptx"]["expected_notes_contain"]:
            assert fragment in joined, f"missing note fragment: {fragment!r}"


# ---------------------------------------------------------------------------
# Format detection — by magic bytes (zip + central-dir inspection)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _have("docx", "openpyxl", "pptx"),
    reason="Office deps required",
)
class TestFormatDetection:
    """Files with their extension stripped should still detect correctly via
    central-directory inspection. Validates the magic-byte path in
    nom.doc.stages._format_from_zip_bytes."""

    def test_docx_detected_by_bytes(self, ground_truth: dict, tmp_path: Path) -> None:
        from nom.doc import Context, Load

        src = (DIR / ground_truth["docx"]["file"]).read_bytes()
        ctx = Context(source=src)
        Load().run(ctx)
        assert ctx.fmt == "docx"

    def test_xlsx_detected_by_bytes(self, ground_truth: dict) -> None:
        from nom.doc import Context, Load

        src = (DIR / ground_truth["xlsx"]["file"]).read_bytes()
        ctx = Context(source=src)
        Load().run(ctx)
        assert ctx.fmt == "xlsx"

    def test_pptx_detected_by_bytes(self, ground_truth: dict) -> None:
        from nom.doc import Context, Load

        src = (DIR / ground_truth["pptx"]["file"]).read_bytes()
        ctx = Context(source=src)
        Load().run(ctx)
        assert ctx.fmt == "pptx"
