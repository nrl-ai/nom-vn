"""Pipeline stage implementations.

v0.0.3 ships **real** Load and Parse stages. OCR / Extract / Validate remain
placeholders for v0.1. The Stage protocol and pipeline shape are stable —
code written against the v0.0.x preview API will keep working.

See ``docs/PIPELINE.md`` for the picks each real stage will use.
"""

from __future__ import annotations

from pathlib import Path
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


# Canonical mime/format detection. Magic-bytes-aware for the formats we care
# about; falls back to extension. No third-party deps.
_PDF_MAGIC = b"%PDF-"
_IMAGE_MAGICS: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",  # JPEG magic prefix (FF D8 FF)
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"II*\x00": "image/tiff",  # little-endian TIFF
    b"MM\x00*": "image/tiff",  # big-endian TIFF
    b"RIFF": "image/webp",  # WEBP starts with RIFF (full check below)
    b"BM": "image/bmp",
}

_TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".log"}


def _detect_format(source: str | Path | bytes) -> str:
    """Return ``"pdf"``, ``"image"``, or ``"text"``.

    For bytes: read the first 16 bytes and match magic numbers.
    For path: try magic first, fall back to extension.
    """
    if isinstance(source, bytes):
        head = source[:16]
        return _format_from_head(head, ext="")
    path = Path(source)
    if path.is_file():
        with path.open("rb") as f:
            head = f.read(16)
        ext = path.suffix.lower()
        return _format_from_head(head, ext=ext)
    # Path doesn't exist (yet) — extension only
    return _format_from_extension(path.suffix.lower())


def _format_from_head(head: bytes, *, ext: str) -> str:
    if head.startswith(_PDF_MAGIC):
        return "pdf"
    for magic in _IMAGE_MAGICS:
        if head.startswith(magic):
            # WEBP requires the WEBP token at offset 8
            if magic == b"RIFF" and len(head) >= 12 and head[8:12] != b"WEBP":
                continue
            return "image"
    return _format_from_extension(ext)


def _format_from_extension(ext: str) -> str:
    if ext == ".pdf":
        return "pdf"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".tiff", ".tif", ".bmp", ".webp"}:
        return "image"
    if ext in _TEXT_EXTENSIONS:
        return "text"
    # Default: treat unknowns as text. Keeps the pipeline running rather than
    # blowing up on a misnamed file.
    return "text"


class Load:
    """Detect input format and route to the next stage.

    v0.0.3 implementation: pure stdlib. Reads ``ctx.source`` (path/bytes),
    sets ``ctx.fmt`` ∈ {``"pdf"``, ``"image"``, ``"text"``}, populates
    ``ctx.metadata["bytes"]`` if source was a path so downstream stages can
    read it without a second disk hit.
    """

    name = "Load"

    def run(self, ctx: Context) -> Context:
        fmt = _detect_format(ctx.source)
        ctx.fmt = fmt
        # Cache bytes on context if we read from disk; downstream stages reuse.
        if isinstance(ctx.source, str | Path):
            path = Path(ctx.source)
            if path.is_file():
                ctx.metadata["path"] = path
                ctx.metadata["bytes"] = path.read_bytes()
        elif isinstance(ctx.source, bytes):
            ctx.metadata["bytes"] = ctx.source
        return ctx


class Parse:
    """Extract native text + layout from PDFs (skip if image/text).

    v0.0.3 implementation: uses ``pdfplumber`` (MIT) when installed.
    pdfplumber is slower than PyMuPDF (AGPL) but our default keeps us in
    permissive-license territory. Power users can swap to PyMuPDF.

    For ``"image"`` inputs: leaves ``ctx.pages_text`` empty and adds a single
    OCR-needed entry — the OCR stage handles it.

    For ``"text"`` inputs: reads ``ctx.metadata["bytes"]`` as UTF-8 and
    populates ``ctx.pages_text`` with one entry.

    Args:
        backend: ``"pdfplumber"`` (default, MIT) or ``"pymupdf"`` (AGPL,
            faster — opt-in for users who can comply with the license).
    """

    name = "Parse"

    def __init__(self, backend: str = "pdfplumber") -> None:
        if backend not in ("pdfplumber", "pymupdf"):
            raise ValueError(f"backend must be 'pdfplumber' or 'pymupdf', got {backend!r}")
        self.backend = backend

    def run(self, ctx: Context) -> Context:
        if ctx.fmt is None:
            raise RuntimeError("Parse stage requires ctx.fmt to be set — run Load first.")

        if ctx.fmt == "text":
            data = ctx.metadata.get("bytes", b"")
            ctx.pages_text = [data.decode("utf-8", errors="replace")]
            ctx.text = ctx.pages_text[0]
            return ctx

        if ctx.fmt == "image":
            # Parse skips images — OCR stage handles them.
            ctx.pages_text = [""]
            ctx.needs_ocr = [0]
            return ctx

        # PDF path
        if self.backend == "pdfplumber":
            self._parse_pdf_pdfplumber(ctx)
        else:
            self._parse_pdf_pymupdf(ctx)
        return ctx

    def _parse_pdf_pdfplumber(self, ctx: Context) -> None:
        try:
            import pdfplumber
        except ImportError as exc:
            raise ImportError(
                "Parse(backend='pdfplumber') requires pdfplumber. "
                "Install with: pip install nom-vn[doc]"
            ) from exc

        data = ctx.metadata.get("bytes")
        if data is None:
            raise RuntimeError("Parse: no bytes available on context.")

        import io

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages: list[str] = []
            layouts: list[dict[str, Any]] = []
            needs_ocr: list[int] = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages.append(text)
                layouts.append(
                    {
                        "page": i,
                        "width": page.width,
                        "height": page.height,
                        "n_chars": len(text),
                    }
                )
                if not text.strip():
                    needs_ocr.append(i)

        ctx.pages_text = pages
        ctx.pages_layout = layouts
        ctx.needs_ocr = needs_ocr
        # Concatenated text for stages that don't care about page boundaries.
        ctx.text = "\n\n".join(pages)

    def _parse_pdf_pymupdf(self, ctx: Context) -> None:
        try:
            import fitz
        except ImportError as exc:
            raise ImportError(
                "Parse(backend='pymupdf') requires PyMuPDF (AGPL). "
                "Install with: pip install pymupdf"
            ) from exc

        data = ctx.metadata.get("bytes")
        if data is None:
            raise RuntimeError("Parse: no bytes available on context.")

        doc = fitz.open(stream=data, filetype="pdf")
        try:
            pages: list[str] = []
            layouts: list[dict[str, Any]] = []
            needs_ocr: list[int] = []
            for i, page in enumerate(doc):
                text = page.get_text()
                pages.append(text)
                layouts.append(
                    {
                        "page": i,
                        "width": page.rect.width,
                        "height": page.rect.height,
                        "n_chars": len(text),
                    }
                )
                if not text.strip():
                    needs_ocr.append(i)
        finally:
            doc.close()

        ctx.pages_text = pages
        ctx.pages_layout = layouts
        ctx.needs_ocr = needs_ocr
        ctx.text = "\n\n".join(pages)


# ---------------------------------------------------------------------------
# Placeholders for v0.1 (still raise NotImplementedError).
# ---------------------------------------------------------------------------


class _PlaceholderStage:
    """Stage that documents its eventual behavior and refuses to run."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx: Context) -> Context:
        raise NotImplementedError(
            f"nom.doc.stages.{self.name} ships in v0.1. "
            f"Track release: https://github.com/nrl-ai/nom"
        )


class OCR(_PlaceholderStage):
    """Run OCR on pages flagged as scans.

    v0.1 default backend: VietOCR (Transformer, VN-specialized).
    Fallbacks: PaddleOCR PP-OCRv5, Tesseract 5+vie.

    Args:
        engine: ``"vietocr"`` | ``"paddleocr"`` | ``"tesseract"`` | ``"auto"``
    """

    def __init__(self, engine: str = "auto") -> None:
        super().__init__("OCR")
        self.engine = engine


class Normalize:
    """Apply ``nom.text`` cleanup to the parsed text.

    What it does (v0.0.3 implementation):
      1. Joins ``ctx.pages_text`` into ``ctx.text`` (page-separator: blank line).
      2. Applies Unicode NFC normalization.
      3. Applies VN-aware text normalization (whitespace + punctuation cleanup).
      4. Optionally applies diacritic restoration (off by default — the rule-
         based path corrupts text with high diacritic content; useful only on
         OCR-stripped text).

    Args:
        restore_diacritics: when True, apply ``nom.text.fix_diacritics`` to
            the joined text. Default False because the v0.0.1 rule-based
            implementation only helps OCR-stripped input — it can damage
            already-correct VN text. v0.0.3 plans an ML-backed restoration
            that will be safe to run unconditionally; until then this stays
            opt-in.
    """

    name = "Normalize"

    def __init__(self, restore_diacritics: bool = False) -> None:
        self.restore_diacritics = restore_diacritics

    def run(self, ctx: Context) -> Context:
        # Lazy import to keep the placeholder stages dep-free.
        from nom.text import fix_diacritics, normalize, text_normalize

        def _clean(s: str) -> str:
            out = text_normalize(normalize(s))
            return fix_diacritics(out) if self.restore_diacritics else out

        # Apply normalization per-page so we can preserve page boundaries in
        # ctx.text. text_normalize collapses internal whitespace, so joining
        # raw pages first would lose the page break.
        if ctx.pages_text:
            ctx.pages_text = [_clean(p) for p in ctx.pages_text]
            ctx.text = "\n\n".join(ctx.pages_text)
        elif ctx.text:
            # Defensive: if Parse didn't populate pages_text but did set
            # ctx.text directly (unusual), still normalize it.
            ctx.text = _clean(ctx.text)
        return ctx


class Extract(_PlaceholderStage):
    """Schema-driven LLM extraction (default backend: Instructor + Pydantic).

    Args:
        llm: an ``LLM`` adapter from ``nom.llm`` (Ollama / OpenAI / Anthropic).
            Required — Nôm doesn't bundle a model.
    """

    def __init__(self, llm: Any) -> None:
        super().__init__("Extract")
        self.llm = llm


class Validate(_PlaceholderStage):
    """Validate the LLM's structured output against the user-provided schema.

    Uses Pydantic v2. Coerces shorthand types defined in ``nom.doc.schemas``.
    """

    def __init__(self) -> None:
        super().__init__("Validate")
