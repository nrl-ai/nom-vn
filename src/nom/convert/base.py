"""Shared types for the convert module."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ConversionStats"]


@dataclass(frozen=True, slots=True)
class ConversionStats:
    """Summary of a single conversion run.

    ``pages_text_extracted`` are pages where we got the text directly
    from the source (PDF text layer, etc.). ``pages_ocred`` are pages
    we had to fall back to OCR for. ``chars_out`` is the total output
    character count — useful as a "did anything come through" check.
    """

    n_pages: int
    pages_text_extracted: int
    pages_ocred: int
    chars_out: int
    ocr_language: str
