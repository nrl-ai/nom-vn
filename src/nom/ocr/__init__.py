"""Vietnamese OCR — handwriting-specialised wrappers.

For *printed*-text OCR see :mod:`nom.convert.image_to_docx` (Tesseract;
0 % CER on clean print, but 69 % CER on handwriting per internal bench
on the brianhuster dataset). This module ships specialist VLM wrappers
that handle the handwriting / form / ID-card cases where Tesseract
collapses.

Today: :class:`VinternHandwritingOcr` (5CD-AI/Vintern-1B-v3_5, MIT,
safetensors, sub-1 B). Future: TrOCR-handwritten + VN fine-tune for
line-level pipelines, once the base model bench numbers land.

The :class:`HandwritingOcr` Protocol is intentionally minimal — pass
a path or PIL image, get back text + a confidence score that callers
can threshold for fallback to Tesseract on high-confidence prints.
"""

from nom.ocr.handwriting import (
    HandwritingOcr,
    HandwritingResult,
    VinternHandwritingOcr,
)

__all__ = [
    "HandwritingOcr",
    "HandwritingResult",
    "VinternHandwritingOcr",
]
