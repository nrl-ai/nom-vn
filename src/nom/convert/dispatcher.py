"""Pick the right converter by source file extension."""

from __future__ import annotations

from pathlib import Path

from nom.convert.base import ConversionStats
from nom.convert.image_to_docx import image_to_docx
from nom.convert.pdf_to_docx import pdf_to_docx

__all__ = ["SUPPORTED_INPUTS", "convert_to_docx"]

_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"})

SUPPORTED_INPUTS = frozenset({".pdf", *_IMAGE_EXTS})


def convert_to_docx(
    src: Path | str,
    dst: Path | str,
    *,
    ocr_language: str = "vie+eng",
) -> ConversionStats:
    """Convert ``src`` to a ``.docx`` at ``dst``, dispatching by extension.

    Supported source formats: ``.pdf``, plus common image formats
    (``.png``, ``.jpg``, ``.tiff``, ``.bmp``, ``.webp``). Anything
    else raises ``ValueError`` — extend the dispatcher to add new
    converters.
    """
    src_path = Path(src)
    suffix = src_path.suffix.lower()

    if suffix == ".pdf":
        return pdf_to_docx(src, dst, ocr_language=ocr_language)
    if suffix in _IMAGE_EXTS:
        return image_to_docx(src, dst, ocr_language=ocr_language)
    raise ValueError(f"unsupported source format {suffix!r}; supported: {sorted(SUPPORTED_INPUTS)}")
