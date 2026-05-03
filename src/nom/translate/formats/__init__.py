"""Format-preserving document walkers.

Each submodule walks a specific document format's structure, calling
the supplied :class:`~nom.translate.Translator` per text unit while
leaving styles, tables, headers, footers, and other non-text structure
intact.

Public surface:

- :func:`translate_file` — pick a walker by file extension
- :func:`translate_docx` / :func:`translate_xlsx` /
  :func:`translate_pptx` / :func:`translate_text` — direct per-format
- ``SUPPORTED_FORMATS`` — set of ``.<ext>`` strings the dispatcher
  knows about
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from nom.translate.base import Translator
from nom.translate.formats.docx import DocxTranslationStats, translate_docx
from nom.translate.formats.pptx import PptxTranslationStats, translate_pptx
from nom.translate.formats.text import TextTranslationStats, translate_text
from nom.translate.formats.xlsx import XlsxTranslationStats, translate_xlsx

__all__ = [
    "SUPPORTED_FORMATS",
    "DocxTranslationStats",
    "PptxTranslationStats",
    "TextTranslationStats",
    "XlsxTranslationStats",
    "translate_docx",
    "translate_file",
    "translate_pptx",
    "translate_text",
    "translate_xlsx",
]

_TEXT_EXTS = frozenset({".txt", ".md", ".markdown", ".rst"})

SUPPORTED_FORMATS = frozenset({".docx", ".xlsx", ".pptx", *_TEXT_EXTS})


def translate_file(
    src: Path | str,
    dst: Path | str,
    translator: Translator,
    *,
    progress_cb: Callable[[float], None] | None = None,
) -> Any:
    """Translate ``src`` to ``dst``, dispatching by file extension.

    Returns the per-format stats dataclass — different formats have
    different counts (paragraphs vs cells), so callers should treat
    the returned object via its dataclass-fields rather than by a
    common interface.

    ``progress_cb`` (when given) is forwarded to the format walker;
    it's invoked with a ``[0, 1]`` fraction after each translation unit.

    Raises ``ValueError`` for unsupported extensions.
    """
    src_path = Path(src)
    suffix = src_path.suffix.lower()

    if suffix == ".docx":
        return translate_docx(src, dst, translator, progress_cb=progress_cb)
    if suffix == ".xlsx":
        return translate_xlsx(src, dst, translator, progress_cb=progress_cb)
    if suffix == ".pptx":
        return translate_pptx(src, dst, translator, progress_cb=progress_cb)
    if suffix in _TEXT_EXTS:
        return translate_text(src, dst, translator, progress_cb=progress_cb)
    raise ValueError(
        f"unsupported source format {suffix!r}; supported: {sorted(SUPPORTED_FORMATS)}"
    )
