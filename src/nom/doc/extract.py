"""Top-level convenience: ``nom.doc.extract(source, schema, llm) -> dict``.

Wraps the default 6-stage pipeline. Use :class:`nom.doc.Pipeline` directly
if you need to customize stages (different OCR engine, skip OCR for
known-clean PDFs, custom prompts, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract(
    source: str | Path | bytes,
    *,
    schema: dict[str, Any],
    llm: Any,
) -> dict[str, Any]:
    """Extract structured fields from a Vietnamese document.

    Convenience wrapper around :func:`nom.doc.default_pipeline`. Equivalent
    to::

        from nom.doc import default_pipeline
        result = default_pipeline(llm).run(source, schema=schema)

    Args:
        source: path to PDF / image / text file, or raw bytes.
        schema: dict mapping field name → type or shorthand string. See
            :class:`nom.doc.schemas.SchemaResolver` for supported shorthand:
            ``"date"``, ``"amount_vnd"``, ``"party"``, ``"str"``, ``"int"``,
            ``"float"``, ``"bool"``. Direct types also accepted.
        llm: an :class:`nom.llm.LLM` adapter (Ollama / OpenAI / Anthropic).
            Required — Nôm doesn't bundle a model.

    Returns:
        Dict matching the keys of ``schema`` with extracted, validated,
        VN-coerced values (e.g. ``"14/3/2025"`` → ``date(2025, 3, 14)``,
        ``"1.500.000.000"`` → ``1500000000``).

    Example:
        >>> from nom.doc import extract
        >>> from nom.llm import Ollama
        >>> result = extract(
        ...     "hop_dong.pdf",
        ...     schema={
        ...         "so_hop_dong": str,
        ...         "ngay_ky": "date",
        ...         "tong_gia_tri": "amount_vnd",
        ...         "ben_a": "party",
        ...         "ben_b": "party",
        ...     },
        ...     llm=Ollama(model="qwen3:8b"),
        ... )
    """
    from nom.doc.pipeline import default_pipeline

    pipe = default_pipeline(llm)
    return pipe.run(source, schema=schema)
