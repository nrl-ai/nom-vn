"""Tag-protection: preserve per-run styling across translation.

The walker's v0 strategy collapses every paragraph to its first run's
style. v1 (this module) tries to preserve intra-paragraph styling by
replacing run boundaries with stable placeholders before translation,
then re-distributing the translated text into the original runs. If
the LLM mishandles the placeholders (drops, reorders, duplicates),
we fall back to v0 cleanly so the output is never garbled.

The placeholder syntax uses double-mathematical brackets ``⟦N⟧``
(U+27E6 / U+27E7) — these survive most BPE / sentencepiece tokenizers
without splitting, are visually unambiguous, and almost never appear
in user prose. Compared with ``{0}``, ``<g0/>``, or ``[[0]]``, they:

- are not interpreted as code by Python-aware models,
- are not interpreted as markup by HTML-aware models,
- don't collide with the user's curly-brace usage.

OSS prior art studied:

- **Okapi Framework** (Apache-2.0): the canonical XLIFF tag-protection
  reference. Uses ``<g id='1'>`` markers identical in spirit; we picked
  brackets to spare the LLM from XML-validation drift.
- **OmegaT** (GPL-3): same XLIFF-marker approach plus glossary
  injection. Their fall-through-on-malformed strategy is what we
  mirror — never garble the doc.
"""

from __future__ import annotations

import re
from typing import Any

from nom.translate.base import Translator

__all__ = ["TagProtectResult", "translate_with_tag_protection"]


_PLACEHOLDER_RE = re.compile(r"⟦(\d+)⟧")


class TagProtectResult:
    """Outcome of one :func:`translate_with_tag_protection` call.

    ``run_texts[i]`` is the translated text that should be written to
    run ``i`` of the paragraph. ``protected`` reports whether the
    placeholder round-trip succeeded; ``False`` means the caller should
    fall back to v0 collapse (write all translated text into the first
    run, clear the rest).
    """

    __slots__ = ("fallback_text", "protected", "run_texts")

    def __init__(
        self,
        *,
        protected: bool,
        run_texts: list[str],
        fallback_text: str,
    ) -> None:
        self.protected = protected
        self.run_texts = run_texts
        self.fallback_text = fallback_text


def translate_with_tag_protection(
    run_texts: list[str],
    translator: Translator,
) -> TagProtectResult:
    """Translate a list of run texts as one unit, preserving boundaries.

    For one or zero runs there is nothing to protect — translate the
    concatenation directly and return ``protected=True``.

    For two or more runs:

    1. Build a source string with ``⟦0⟧``, ``⟦1⟧``, ... markers between
       runs.
    2. Translate via the supplied :class:`Translator`, passing a
       ``hint`` that asks for placeholder preservation.
    3. Parse the translated string. If every placeholder is present
       exactly once and in order (0, 1, ..., N), distribute the
       inter-placeholder text into the corresponding runs.
    4. Otherwise: emit a v0 fallback (full translated text → first run,
       rest cleared). The caller is told to apply this via
       ``protected=False``.
    """
    if not run_texts:
        return TagProtectResult(protected=True, run_texts=[], fallback_text="")

    if len(run_texts) == 1:
        translated = translator.translate(run_texts[0])
        return TagProtectResult(
            protected=True,
            run_texts=[translated],
            fallback_text=translated,
        )

    source = _build_protected_source(run_texts)
    hint = (
        "Preserve every ⟦N⟧ placeholder exactly as-is, in the same "
        "order. Do not translate, remove, or duplicate them."
    )
    translated = translator.translate(source, hint=hint)

    distributed = _try_distribute(translated, n_runs=len(run_texts))
    if distributed is None:
        # Fallback: strip placeholders from the translation (in case
        # they survived) and return as v0 collapse.
        cleaned = _PLACEHOLDER_RE.sub("", translated).strip()
        return TagProtectResult(
            protected=False,
            run_texts=[],
            fallback_text=cleaned,
        )

    return TagProtectResult(
        protected=True,
        run_texts=distributed,
        fallback_text=translated,
    )


def _build_protected_source(run_texts: list[str]) -> str:
    """Concatenate runs with placeholders BEFORE each, plus a final
    closing placeholder. ``["A", "B", "C"]`` → ``"⟦0⟧A⟦1⟧B⟦2⟧C⟦3⟧"``."""
    parts: list[str] = []
    for i, text in enumerate(run_texts):
        parts.append(f"⟦{i}⟧")
        parts.append(text)
    parts.append(f"⟦{len(run_texts)}⟧")
    return "".join(parts)


def _try_distribute(translated: str, *, n_runs: int) -> list[str] | None:
    """Split ``translated`` at placeholder boundaries into ``n_runs`` pieces.

    Returns ``None`` if the placeholders are missing, out of order, or
    duplicated — telling the caller to fall back to v0 collapse.
    """
    pieces: list[str] = []
    last_end = 0
    expected_idx = 0
    for match in _PLACEHOLDER_RE.finditer(translated):
        idx = int(match.group(1))
        if idx != expected_idx:
            return None
        if idx > 0:
            # Capture the text between the previous placeholder and this one
            pieces.append(translated[last_end : match.start()])
        last_end = match.end()
        expected_idx += 1

    # We expect placeholders 0..n_runs (inclusive) — n_runs+1 markers
    if expected_idx != n_runs + 1:
        return None
    return pieces


def detect_length_warning(
    source_chars: int,
    target_chars: int,
    *,
    threshold: float = 1.5,
) -> str | None:
    """Return a one-line warning when ``target`` is more than ``threshold``x
    longer than ``source``. Used to flag paragraphs that may overflow
    fixed-width containers (table cells, bordered text boxes).
    """
    if source_chars <= 0:
        return None
    ratio = target_chars / source_chars
    if ratio < threshold:
        return None
    return (
        f"target is {ratio:.1f}x source ({source_chars}→{target_chars} chars); "
        f"may overflow fixed-width containers"
    )


def _ensure_translator_protocol(t: Any) -> Translator:
    """Tiny runtime check used by tests."""
    if not hasattr(t, "translate"):
        raise TypeError(f"expected a Translator, got {type(t).__name__}")
    return t  # type: ignore[no-any-return]
