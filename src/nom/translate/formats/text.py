"""Plain-text and markdown translation.

Splits on blank lines (``\\n\\s*\\n+``) so paragraphs of arbitrary line
length get translated as single units — this matches how human readers
parse prose, and gives the LLM enough context to disambiguate pronouns.

Markdown caveat: in v0 we treat ``.md`` like plain text, which means:

- Code fences (``` ``` ... ``` ```) **are** translated. v0 accepts this;
  most users translating markdown care about prose, not code, and we
  leave the fix (skip code blocks) to v0.5.
- Header markers (``#``) and list markers (``-``, ``1.``) come along
  with the paragraph and the LLM usually preserves them.
- Inline code spans (``code``) and emphasis (``*emphasis*``) are
  generally preserved by an LLM that's prompted to keep formatting.

Encoding is UTF-8. NFC-normalize on read AND write.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nom.translate.base import Translator

__all__ = ["TextTranslationStats", "translate_text"]


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")


@dataclass(frozen=True, slots=True)
class TextTranslationStats:
    """Summary of a single :func:`translate_text` run."""

    paragraphs_translated: int
    paragraphs_skipped: int
    paragraphs_failed: int
    chars_in: int
    chars_out: int


def translate_text(
    src: Path | str,
    dst: Path | str,
    translator: Translator,
    *,
    progress_cb: Callable[[float], None] | None = None,
) -> TextTranslationStats:
    """Translate a plain-text or markdown file. UTF-8 in / UTF-8 out, NFC.

    ``progress_cb``, when supplied, is called with a ``[0.0, 1.0]``
    fraction after each translation unit. The runner that owns the
    callback can also raise from inside it (e.g. cooperative cancel)
    and the walker will propagate.
    """
    src_path = Path(src)
    dst_path = Path(dst)
    if not src_path.exists():
        raise FileNotFoundError(f"text source not found: {src_path}")

    raw = src_path.read_text(encoding="utf-8")
    raw = unicodedata.normalize("NFC", raw)

    paragraphs = _PARAGRAPH_SPLIT.split(raw)
    out_paragraphs: list[str] = []

    translated_count = 0
    skipped_count = 0
    failed_count = 0
    chars_in = 0
    chars_out = 0
    total = max(1, len(paragraphs))

    for idx, para in enumerate(paragraphs):
        if not para.strip():
            out_paragraphs.append(para)
            skipped_count += 1
        else:
            chars_in += len(para)
            try:
                translated = translator.translate(para)
                chars_out += len(translated)
                out_paragraphs.append(translated)
                translated_count += 1
            except Exception:
                out_paragraphs.append(para)
                failed_count += 1
        if progress_cb is not None:
            progress_cb((idx + 1) / total)

    output = "\n\n".join(out_paragraphs)
    output = unicodedata.normalize("NFC", output)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(output, encoding="utf-8")

    return TextTranslationStats(
        paragraphs_translated=translated_count,
        paragraphs_skipped=skipped_count,
        paragraphs_failed=failed_count,
        chars_in=chars_in,
        chars_out=chars_out,
    )
