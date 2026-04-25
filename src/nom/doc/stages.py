"""Pipeline stage implementations.

All six default stages are real as of v0.0.3:

  - Load (pure stdlib, magic-byte format detection)
  - Parse (pdfplumber MIT default; pymupdf AGPL opt-in)
  - OCR (pytesseract + vie traineddata)
  - Normalize (nom.text)
  - Extract (LLM via nom.llm + Pydantic schema with retries)
  - Validate (nom.doc.schemas SchemaResolver, Pydantic v2)

See ``docs/PIPELINE.md`` for the per-stage component picks and rationale.
"""

from __future__ import annotations

import json
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


class OCR:
    """Run OCR on pages flagged as scans (or on direct image inputs).

    v0.0.3 implementation: Tesseract via ``pytesseract`` (Apache 2.0).
    Tesseract is the most-audited OCR engine in the open-source world,
    and pytesseract is a thin wrapper (~hundreds of lines). Tesseract
    binary is system-installed: ``apt install tesseract-ocr tesseract-ocr-vie``
    on Debian/Ubuntu, or ``brew install tesseract tesseract-lang`` on
    macOS.

    For Vietnamese, this stage runs Tesseract with ``-l vie``. Per
    upstream docs, the ``vie.traineddata`` was trained on Times New Roman,
    Arial, Verdana, Courier New — accuracy is best on those fonts and
    inputs scanned at 200-400 DPI.

    Future v0.x backends in docs/PIPELINE.md (VietOCR Transformer,
    PaddleOCR PP-OCRv5) will integrate as opt-in alternatives once we
    have measured accuracy comparisons on a curated VN scan corpus.

    Reads:
        - ``ctx.fmt`` — must be ``"image"`` (else this is a no-op).
        - ``ctx.metadata["bytes"]`` — raw image bytes from Load.
        - Or for PDF inputs: pages flagged in ``ctx.needs_ocr`` (v0.1.1).

    Writes:
        - ``ctx.pages_text`` — the OCR'd text per page.
        - ``ctx.text`` — concatenated.
        - ``ctx.needs_ocr`` — cleared.

    Args:
        lang: Tesseract language code. Default ``"vie"``. Use ``"vie+eng"``
            for mixed Vietnamese/English documents.
        config: extra Tesseract config flags (e.g. ``"--psm 6"`` for
            uniform block of text). Default empty.
    """

    name = "OCR"

    def __init__(self, lang: str = "vie", config: str = "") -> None:
        self.lang = lang
        self.config = config

    def run(self, ctx: Context) -> Context:
        if ctx.fmt is None:
            raise RuntimeError("OCR requires ctx.fmt — run Load first.")

        # No-op for non-image, non-OCR-flagged inputs.
        if ctx.fmt != "image" and not ctx.needs_ocr:
            return ctx

        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            missing = "pytesseract" if "pytesseract" in str(exc) else "Pillow"
            raise ImportError(
                f"OCR stage requires {missing}. " f"Install with: pip install nom-vn[doc]"
            ) from exc

        if ctx.fmt == "image":
            data = ctx.metadata.get("bytes")
            if data is None:
                raise RuntimeError("OCR: no image bytes available on context.")
            text = self._ocr_bytes(data, pytesseract, image_module=Image)
            ctx.pages_text = [text]
            ctx.text = text
            ctx.needs_ocr = []
        elif ctx.needs_ocr:
            # PDF with scanned pages — v0.1.1 will render the page to image
            # via pdfplumber.page.to_image() and OCR each. For v0.0.3 we
            # emit a clear error so users know what to do.
            raise NotImplementedError(
                "OCR for PDF-with-scanned-pages ships in v0.1.1. "
                "For now, convert your scanned PDF to images first "
                "(e.g. with pdftoppm) and pass each image separately. "
                f"Pages needing OCR: {ctx.needs_ocr}"
            )

        return ctx

    def _ocr_bytes(self, data: bytes, pytesseract: Any, *, image_module: Any) -> str:
        import io

        image = image_module.open(io.BytesIO(data))
        # Tesseract works best on RGB/grayscale; convert if needed.
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        text: str = pytesseract.image_to_string(
            image,
            lang=self.lang,
            config=self.config,
        )
        # Tesseract sometimes emits trailing form-feeds and excessive
        # whitespace — strip and collapse.
        return text.strip()


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


class Extract:
    """Schema-driven LLM extraction with auto-retry on validation failure.

    v0.0.3 real implementation: builds a JSON schema from ``ctx.schema``,
    prompts the LLM with the parsed text + the schema, parses the JSON
    response, and retries with error feedback if the model produces
    invalid output. This is the same pattern as the ``instructor`` library
    (~30 LOC, no extra dep).

    Reads:
        - ``ctx.text`` — cleaned text from Normalize
        - ``ctx.schema`` — user-provided schema dict
    Writes:
        - ``ctx.output`` — raw dict from the LLM (Validate stage will
          coerce it through Pydantic).

    Args:
        llm: an ``LLM`` adapter from ``nom.llm`` (Ollama / OpenAI / Anthropic).
            Must have a ``.complete(prompt, schema=..., max_tokens=...)``
            method.
        max_retries: how many times to retry with error feedback when the
            LLM produces invalid JSON. Default 3.
        max_tokens: hint forwarded to the LLM. Default 2048.
    """

    name = "Extract"

    def __init__(
        self,
        llm: Any,
        *,
        max_retries: int = 3,
        max_tokens: int = 2048,
    ) -> None:
        if llm is None:
            raise ValueError(
                "Extract requires an LLM adapter. "
                "Use nom.llm.Ollama() for local inference, "
                "or implement the LLM protocol yourself."
            )
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        self.llm = llm
        self.max_retries = max_retries
        self.max_tokens = max_tokens

    def run(self, ctx: Context) -> Context:
        if not ctx.schema:
            raise RuntimeError(
                "Extract requires ctx.schema to be set. "
                "Provide one when calling Pipeline.run(...)."
            )
        if not ctx.text:
            raise RuntimeError("Extract requires ctx.text — did Parse and Normalize run?")

        from nom.doc.schemas import SchemaResolver

        resolver = SchemaResolver(ctx.schema)
        json_schema = resolver.json_schema()

        prompt = self._build_prompt(ctx.text, json_schema)
        last_error: str | None = None

        for attempt in range(1, self.max_retries + 1):
            response = self.llm.complete(
                prompt,
                schema=json_schema,
                max_tokens=self.max_tokens,
            )
            try:
                parsed = self._parse_json(response)
                ctx.output = parsed
                ctx.metadata["extract_attempts"] = attempt
                return ctx
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                # On retry, append error feedback so the model self-corrects.
                # This is the "instructor pattern" — see python.useinstructor.com.
                prompt = (
                    f"{prompt}\n\n"
                    f"=== Previous attempt produced invalid output ===\n"
                    f"Output snippet: {response[:200]}\n"
                    f"Error: {last_error}\n"
                    f"Please respond with ONLY a valid JSON object that "
                    f"strictly matches the schema. No prose, no markdown fences."
                )

        raise RuntimeError(
            f"Extract failed after {self.max_retries} attempts. " f"Last error: {last_error}"
        )

    @staticmethod
    def _build_prompt(text: str, json_schema: dict[str, Any]) -> str:
        schema_str = json.dumps(json_schema, ensure_ascii=False, indent=2)
        return (
            "You are a Vietnamese document-extraction assistant. Extract the "
            "fields described by the JSON schema below from the document "
            "text. Respond with ONLY a valid JSON object — no prose, no "
            "markdown fences, no explanations.\n\n"
            "Vietnamese conventions to preserve:\n"
            "- Dates: 'ngày 14 tháng 3 năm 2025' or '14/3/2025' formats are OK.\n"
            "- Amounts: VND amounts use '.' as thousands separator (e.g., "
            "'1.500.000.000').\n"
            "- Diacritics: keep tone marks exactly as in the source.\n\n"
            f"=== Schema ===\n{schema_str}\n\n"
            f"=== Document ===\n{text}\n\n"
            "=== Response (JSON only) ==="
        )

    @staticmethod
    def _parse_json(response: str) -> dict[str, Any]:
        """Parse the LLM's JSON response, tolerant of markdown fences."""
        s = response.strip()
        # Strip ```json ... ``` and ``` ... ``` markdown fences if the model
        # ignored our instructions.
        if s.startswith("```"):
            # Drop the first fence line and the closing fence.
            lines = s.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            s = "\n".join(lines)
        result = json.loads(s)
        if not isinstance(result, dict):
            raise ValueError(f"Expected JSON object, got {type(result).__name__}")
        return result


class Validate:
    """Validate the LLM's structured output against the user-provided schema.

    v0.0.3 real implementation: uses :class:`nom.doc.schemas.SchemaResolver`
    to build a runtime Pydantic model from the user's schema dict, then
    validates ``ctx.output`` against it.

    Reads:
        - ``ctx.output`` — raw dict from Extract stage
        - ``ctx.schema`` — user-provided schema spec
    Writes:
        - ``ctx.output`` — validated + coerced dict (same keys, parsed values)
    """

    name = "Validate"

    def run(self, ctx: Context) -> Context:
        if not ctx.schema:
            raise RuntimeError(
                "Validate stage requires ctx.schema to be set. "
                "Provide a schema when calling Pipeline.run(...)."
            )
        if not ctx.output:
            raise RuntimeError(
                "Validate stage requires ctx.output to be populated by Extract. "
                "Did the Extract stage run?"
            )

        from nom.doc.schemas import SchemaResolver

        resolver = SchemaResolver(ctx.schema)
        ctx.output = resolver.validate(ctx.output)
        return ctx
