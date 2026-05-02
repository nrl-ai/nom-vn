"""Format-preserving .docx translation walker.

Walks the python-docx tree (body, tables, headers / footers across all
sections) and translates each paragraph as a unit.

**v0 strategy: paragraph-level styling.** All runs in a paragraph
(including those nested inside hyperlinks) are concatenated, translated
as one string, written into the first run, with subsequent runs
cleared. The first run's style propagates across the whole paragraph.

Trade-off: mixed-style paragraphs lose intra-paragraph styling. A
sentence with one bold word inside an otherwise-plain paragraph becomes
plain after translation. Paragraph-level styling — headings, list
levels, font, alignment, color, spacing — is fully preserved.

Out of scope for v0 (passes through unchanged):

- Footnotes, endnotes, comments
- Tracked changes, revisions
- Embedded objects (charts, SmartArt, OLE)
- Equations, math content (`<m:oMath>`)
- Image alt-text

A v0.5 path with proportional run-redistribution and a v1 path with
mBERT word-alignment are described in the design doc; both deferred
until user feedback proves they're needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nom.translate.base import Translator

if TYPE_CHECKING:
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run

__all__ = ["DocxTranslationStats", "translate_docx"]


@dataclass(frozen=True, slots=True)
class DocxTranslationStats:
    """Summary of a single :func:`translate_docx` run.

    ``paragraphs_translated`` counts paragraphs where the translator
    returned successfully. ``paragraphs_skipped`` are empty / whitespace
    paragraphs we passed through. ``paragraphs_failed`` are paragraphs
    where the translator raised — those are left unchanged in the
    output, so the doc remains valid even when the model trips on a
    specific input.
    """

    paragraphs_translated: int
    paragraphs_skipped: int
    paragraphs_failed: int
    chars_in: int
    chars_out: int


def translate_docx(
    src: Path | str,
    dst: Path | str,
    translator: Translator,
) -> DocxTranslationStats:
    """Translate a ``.docx`` file from ``src`` to ``dst``.

    The source file is left untouched. The destination is written
    fresh; any existing file at ``dst`` is overwritten.

    Walks: body paragraphs, body tables (recursively for nested
    tables), and header / footer paragraphs and tables across every
    section (default, first-page, even-page).
    """
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError(
            "Translating .docx requires python-docx. Install with: pip install nom-vn[doc]"
        ) from exc

    src_path = Path(src)
    dst_path = Path(dst)
    if not src_path.exists():
        raise FileNotFoundError(f"docx source not found: {src_path}")

    doc = Document(str(src_path))
    counts = _Counts()
    seen: set[int] = set()

    for para in doc.paragraphs:
        _translate_paragraph(para, translator, counts, seen)
    for tbl in doc.tables:
        _translate_table(tbl, translator, counts, seen)

    for section in doc.sections:
        for region in (
            section.header,
            section.footer,
            section.first_page_header,
            section.first_page_footer,
            section.even_page_header,
            section.even_page_footer,
        ):
            if region is None:
                continue
            for para in region.paragraphs:
                _translate_paragraph(para, translator, counts, seen)
            for tbl in region.tables:
                _translate_table(tbl, translator, counts, seen)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dst_path))
    return counts.freeze()


# ----------------------------------------------------------------------
# Internals


@dataclass
class _Counts:
    translated: int = 0
    skipped: int = 0
    failed: int = 0
    chars_in: int = 0
    chars_out: int = 0

    def freeze(self) -> DocxTranslationStats:
        return DocxTranslationStats(
            paragraphs_translated=self.translated,
            paragraphs_skipped=self.skipped,
            paragraphs_failed=self.failed,
            chars_in=self.chars_in,
            chars_out=self.chars_out,
        )


def _translate_paragraph(
    paragraph: Paragraph,
    translator: Translator,
    counts: _Counts,
    seen: set[int],
) -> None:
    para_id = id(paragraph._element)
    if para_id in seen:
        return
    seen.add(para_id)

    runs = _all_runs_in_order(paragraph)
    if not runs:
        return

    source = "".join(r.text for r in runs)
    if not source.strip():
        counts.skipped += 1
        return

    counts.chars_in += len(source)
    try:
        translated = translator.translate(source)
    except Exception:
        counts.failed += 1
        return

    counts.chars_out += len(translated)
    runs[0].text = translated
    for run in runs[1:]:
        run.text = ""
    counts.translated += 1


def _translate_table(
    table: Table,
    translator: Translator,
    counts: _Counts,
    seen: set[int],
) -> None:
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                _translate_paragraph(para, translator, counts, seen)
            for nested in cell.tables:
                _translate_table(nested, translator, counts, seen)


def _all_runs_in_order(paragraph: Paragraph) -> list[Run]:
    """Every visible run in document order — direct children plus runs
    nested inside ``<w:hyperlink>``. python-docx's ``paragraph.runs``
    skips hyperlink-nested runs, which would silently drop translation
    for hyperlinked text (common in legal docs that cite clause
    numbers as links).
    """
    from docx.oxml.ns import qn
    from docx.text.run import Run

    out: list[Run] = []
    element: Any = paragraph._element
    for child in element.iterchildren():
        tag = child.tag
        if tag == qn("w:r"):
            out.append(Run(child, paragraph))
        elif tag == qn("w:hyperlink"):
            for r_elem in child.findall(qn("w:r")):
                out.append(Run(r_elem, paragraph))
    return out
