"""Document format conversion — PDF / image → DOCX, etc.

Status: v0.1. Companion to :mod:`nom.translate` — convert first into
an editable format, then run translation if desired.

Exports the dispatcher :func:`convert_to_docx`, which picks the right
backend by source-file extension, plus per-format functions for direct
use:

- :func:`nom.convert.pdf_to_docx.pdf_to_docx`
- :func:`nom.convert.image_to_docx.image_to_docx`
"""

from nom.convert.base import ConversionStats
from nom.convert.dispatcher import SUPPORTED_INPUTS, convert_to_docx
from nom.convert.image_to_docx import image_to_docx
from nom.convert.pdf_to_docx import pdf_to_docx

__all__ = [
    "SUPPORTED_INPUTS",
    "ConversionStats",
    "convert_to_docx",
    "image_to_docx",
    "pdf_to_docx",
]
