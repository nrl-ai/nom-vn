"""Document extraction stub for v0.1 preview API.

Final implementation will:
1. Detect input format (PDF, image, raw text).
2. Run OCR if image/scan (pytesseract + post-processing for VN diacritics).
3. Parse layout into blocks (pdfplumber for native PDFs).
4. Call LLM with schema-driven prompt to extract fields.
5. Validate output against schema, return typed dict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = ["extract"]


def extract(
    source: str | Path,
    *,
    schema: dict[str, Any],
    llm: Any | None = None,
) -> dict[str, Any]:
    """Extract structured fields from a Vietnamese document.

    Args:
        source: path to PDF, image, or text file.
        schema: dict mapping field name → type or type-name. Supports
            primitives (str, int, float, bool), date strings, and built-in
            shorthand types (``"date"``, ``"party"``, ``"amount_vnd"``).
        llm: an LLM adapter from ``nom.llm`` (OpenAI, Anthropic, Ollama).
            If None, raises — Nôm doesn't bundle a model.

    Returns:
        Dict matching the keys of ``schema`` with extracted values.

    Raises:
        NotImplementedError: until v0.1 release.

    Example (planned API):
        >>> from nom.doc import extract
        >>> from nom.llm import Ollama
        >>> result = extract("contract.pdf", schema={
        ...     "contract_number": str,
        ...     "signed_date": "date",
        ...     "total_value_vnd": "amount_vnd",
        ... }, llm=Ollama(model="qwen3:8b"))
    """
    raise NotImplementedError(
        "nom.doc.extract is part of v0.1 (planned). "
        "Track release: https://nrl.ai/nom · star github.com/nrl-ai/nom"
    )
