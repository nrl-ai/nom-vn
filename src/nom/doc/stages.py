"""Pipeline stage implementations.

v0.0.1 ships placeholder stages that satisfy the ``Stage`` protocol but
raise ``NotImplementedError`` when run. Real implementations land in v0.1
under the names exported here (``Load``, ``Parse``, ``OCR``, etc.) — code
written against the v0.0.1 names will keep working.

See ``docs/PIPELINE.md`` for the picks each real stage will use.
"""

from __future__ import annotations

from typing import Any

from nom.doc.pipeline import Context

__all__ = [
    "OCR",
    "Extract",
    "Load",
    "Normalize",
    "Parse",
    "Validate",
    "_PlaceholderStage",
]


class _PlaceholderStage:
    """Stage that documents its eventual behavior and refuses to run."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: Context) -> Context:
        raise NotImplementedError(
            f"nom.doc.stages.{self.name} ships in v0.1. "
            f"Track release: https://github.com/nrl-ai/nom"
        )


class Load(_PlaceholderStage):
    """Detect input format from path/bytes; routes to Parse or OCR.

    v0.1 behavior:
        - Read ``ctx.source`` (str/Path → file, bytes → raw).
        - Detect format from extension first, magic bytes fallback.
        - Set ``ctx.fmt`` ∈ {``"pdf"``, ``"image"``, ``"text"``}.
    """

    def __init__(self) -> None:
        super().__init__("Load")


class Parse(_PlaceholderStage):
    """Extract native text + layout from PDF (skip if image/text input).

    v0.1 default backend: PyMuPDF (``fitz``) — fastest by 19x on real PDFs.
    Fallback: pdfplumber for AGPL-incompatible projects.

    Writes:
        - ``ctx.pages_text`` — list of per-page strings
        - ``ctx.pages_layout`` — bbox/font metadata per page
        - ``ctx.needs_ocr`` — page indices where text was empty (= scan)
    """

    def __init__(self, backend: str = "pymupdf") -> None:
        super().__init__("Parse")
        self.backend = backend


class OCR(_PlaceholderStage):
    """Run OCR on pages flagged as scans.

    v0.1 default backend: VietOCR (Transformer, VN-specialized).
    Fallbacks (auto-detected on import): PaddleOCR PP-OCRv5, Tesseract 5+vie.

    Args:
        engine: ``"vietocr"`` (default) | ``"paddleocr"`` | ``"tesseract"`` | ``"auto"``
    """

    def __init__(self, engine: str = "auto") -> None:
        super().__init__("OCR")
        self.engine = engine


class Normalize(_PlaceholderStage):
    """Apply ``nom.text`` cleanup: NFC, diacritic restoration on OCR output.

    Joins ``ctx.pages_text`` into ``ctx.text`` after normalization.

    Args:
        fix_diacritics_backend:
            ``"rules"`` — use the v0.0.1 rule table (zero deps).
            ``"model"`` — v0.0.2: wraps PyVi or DistilBERT-Viet (~90%+).
            ``"llm"`` — v0.1: uses ``ctx.metadata['llm']`` if present.
    """

    def __init__(self, fix_diacritics_backend: str = "rules") -> None:
        super().__init__("Normalize")
        self.fix_diacritics_backend = fix_diacritics_backend


class Extract(_PlaceholderStage):
    """Schema-driven LLM extraction (default backend: Instructor + Pydantic).

    Calls the user-supplied LLM with a constructed prompt that includes
    ``ctx.text`` and the target schema. Uses ``instructor`` to enforce a
    Pydantic-shaped response from any compatible LLM provider.

    Args:
        llm: an ``LLM`` adapter from ``nom.llm`` (Ollama / OpenAI / Anthropic).
            Required — Nôm doesn't bundle a model.
    """

    def __init__(self, llm: Any) -> None:
        super().__init__("Extract")
        self.llm = llm


class Validate(_PlaceholderStage):
    """Validate the LLM's structured output against the user-provided schema.

    Uses Pydantic v2. Coerces shorthand types (``"date"`` → ``datetime.date``,
    ``"amount_vnd"`` → ``int``, etc.) defined in ``nom.doc.schemas``.
    """

    def __init__(self) -> None:
        super().__init__("Validate")
