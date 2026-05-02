"""Format-preserving document walkers.

Each submodule walks a specific document format's structure, calling
the supplied :class:`~nom.translate.Translator` per paragraph / cell /
text unit while leaving styles, tables, headers, footers, and other
non-text structure intact.

Available walkers (v0.1):

- :func:`nom.translate.formats.docx.translate_docx` — Office Open XML
  word-processing documents.

Planned (deferred until the v0.1 walker has user feedback):

- ``xlsx`` — workbook cell walker.
- ``pptx`` — slide / shape / text-frame walker.
- ``pdf`` — text-layer regenerator (best-effort, not pixel-accurate).
"""

from nom.translate.formats.docx import DocxTranslationStats, translate_docx

__all__ = ["DocxTranslationStats", "translate_docx"]
