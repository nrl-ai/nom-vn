"""Composable extraction pipeline.

The pipeline is the spine of ``nom.doc``. It runs a list of ``Stage``
implementations against an input document, threading a ``Context`` that
accumulates state (raw bytes, parsed text, OCR output, extracted dict).

This file ships a real, typed pipeline shape in v0.0.1. The default stages
are scaffolds that raise ``NotImplementedError`` until v0.1 — but the API
is stable. Code written against this preview will continue to work after
the v0.1 release.

See ``docs/PIPELINE.md`` for the picks driving each default stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class Context:
    """Mutable state passed through the pipeline.

    Stages read what they need and write their output in-place. Downstream
    stages can rely on earlier fields being populated; this is enforced by
    each stage's own assertions, not by the Context.
    """

    source: str | Path | bytes
    fmt: str | None = None  # "pdf" / "image" / "text"
    pages_text: list[str] = field(default_factory=list)
    pages_layout: list[dict[str, Any]] = field(default_factory=list)
    needs_ocr: list[int] = field(default_factory=list)  # page indices needing OCR
    text: str = ""
    schema: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class Stage(Protocol):
    """Pipeline stage protocol.

    A stage takes a ``Context``, reads the fields it needs, mutates the
    context in place, and returns it. It must not silently skip work — if
    its preconditions aren't met, raise.

    Stages are stateless aside from configuration in ``__init__``. They
    must be safe to reuse across calls.
    """

    name: str

    def run(self, ctx: Context) -> Context: ...


class Pipeline:
    """Compose stages into a document-extraction pipeline.

    Example (planned v0.1 API):
        >>> from nom.doc.pipeline import Pipeline
        >>> from nom.doc.stages import Load, Parse, OCR, Normalize, Extract, Validate
        >>> from nom.llm import Ollama
        >>> pipe = Pipeline([
        ...     Load(),
        ...     Parse(),
        ...     OCR(engine="vietocr"),
        ...     Normalize(),
        ...     Extract(llm=Ollama(model="qwen3:8b")),
        ...     Validate(),
        ... ])
        >>> result = pipe.run("contract.pdf", schema={"so_hop_dong": str})
    """

    def __init__(self, stages: list[Stage]) -> None:
        if not stages:
            raise ValueError("Pipeline requires at least one stage.")
        self.stages = stages

    def run(
        self,
        source: str | Path | bytes,
        *,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the pipeline against ``source``, returning the validated dict."""
        ctx = Context(source=source, schema=schema or {})
        for stage in self.stages:
            ctx = stage.run(ctx)
        return ctx.output

    def __repr__(self) -> str:
        names = " → ".join(s.name for s in self.stages)
        return f"Pipeline({names})"


def default_pipeline(llm: Any) -> Pipeline:
    """Return the default 6-stage doc-extraction pipeline.

    Composes::

        Load → Parse → OCR → Normalize → Extract → Validate

    Each stage's backend pick is documented in ``docs/PIPELINE.md``.

    Args:
        llm: an :class:`nom.llm.LLM` adapter (Ollama / OpenAI / Anthropic
            or any object implementing ``complete(prompt, schema, max_tokens)``).
            Required because Extract calls into it.

    Example:
        >>> from nom.doc import default_pipeline
        >>> from nom.llm import Ollama
        >>> pipe = default_pipeline(Ollama(model="qwen3:8b"))
        >>> result = pipe.run("contract.pdf", schema={...})

    Notes on extras:
        - Text inputs need only the core (no extras).
        - PDF inputs need ``pip install nom-vn[doc]`` (pdfplumber).
        - Image inputs need ``pip install nom-vn[doc]`` (pytesseract + Pillow)
          plus the system Tesseract binary with ``vie`` traineddata.
        - Any LLM call needs the appropriate adapter's deps (``[llm]``
          for Ollama).
    """
    from nom.doc.stages import OCR, Extract, Load, Normalize, Parse, Validate

    return Pipeline(
        [
            Load(),
            Parse(),
            OCR(),
            Normalize(),
            Extract(llm),
            Validate(),
        ]
    )
