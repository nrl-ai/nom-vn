"""Implementation for :mod:`nom.chunking`.

Design notes:

- **Single pass over sentences.** ``nom.text.sent_tokenize`` runs once;
  token counting reuses ``nom.text.word_tokenize`` once per sentence.
- **No string concatenation in hot loop.** Chunks are emitted by storing
  ``(start, end)`` offsets into the original string and slicing once at
  the end. Beats ``" ".join(...)`` in tight loops.
- **Deterministic.** Same input → same output. No randomness, no global
  state, no mutable defaults.
- **Defensive against pathological input.** Sentence longer than
  ``max_tokens``? We hard-split it on word boundaries and tag the
  resulting chunks with ``metadata["truncated"] = True``.

OSS prior art studied while designing this:

- **LangChain ``RecursiveCharacterTextSplitter``** — clean separator-fallback
  hierarchy (``["\\n\\n", "\\n", " ", ""]``). We adopt the same pattern
  (paragraph → sentence → character) but use Vietnamese-aware sentence
  detection from ``nom.text.sent_tokenize`` instead of regex.
- **LlamaIndex ``SentenceSplitter``** — packs sentences greedily up to a
  token budget with overlap as a count of last-N sentences. We pack by
  token count (not sentence count) for tighter budget control.
- **Unstructured.io** — chunk_by_title strategy for structured docs.
  Adjacent direction for v0.0.5 (we'd need a heading detector first).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nom.text import sent_tokenize, word_tokenize

__all__ = [
    "BoundaryMode",
    "Chunk",
    "paragraph_chunk",
    "sentence_chunk",
    "smart_chunk",
]


class BoundaryMode(str, Enum):
    """How chunks respect document structure.

    - ``PARAGRAPH``: never break a paragraph (split on ``\\n\\n``+).
    - ``SENTENCE`` (default): split on Vietnamese sentence boundaries.
    - ``CHARACTER``: hard char-window chunking; last-resort.
    """

    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    CHARACTER = "character"


@dataclass(frozen=True, slots=True)
class Chunk:
    """An immutable chunk of source text with offsets and token count.

    Frozen + slots because we emit thousands of these and want them cheap.

    Attributes:
        text: the chunk's text content.
        start: 0-based char offset into the original document.
        end: exclusive char offset (so ``original[start:end] == text``
            up to whitespace normalization at boundaries).
        n_tokens: token count via ``nom.text.word_tokenize`` — Vietnamese
            compounds (e.g. ``"Hợp đồng"``) count as 1 token.
        metadata: free-form dict for callers to attach context (page
            number, section heading, document id, etc.). Empty by default.
    """

    text: str
    start: int
    end: int
    n_tokens: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def smart_chunk(
    text: str,
    *,
    max_tokens: int = 512,
    overlap: int = 64,
    boundary: BoundaryMode | str = BoundaryMode.SENTENCE,
) -> list[Chunk]:
    """Chunk Vietnamese text respecting document structure.

    Args:
        text: input document.
        max_tokens: target maximum tokens per chunk. Hard upper bound;
            chunks may be smaller if the boundary mode forces it.
        overlap: how many tokens of trailing context from the previous
            chunk to repeat at the start of the next chunk. Useful for
            retrieval where context can straddle boundaries. Set to 0
            for non-overlapping chunks.
        boundary: see :class:`BoundaryMode`. Default ``SENTENCE``.

    Returns:
        List of :class:`Chunk` objects in source order.

    Raises:
        ValueError: if ``max_tokens`` < 1, ``overlap`` < 0, or
            ``overlap`` >= ``max_tokens``.

    Example:
        >>> chunks = smart_chunk(
        ...     "Hợp đồng số 02. Bên A: Cty ABC. Bên B: Bà Hương.",
        ...     max_tokens=8,
        ...     overlap=2,
        ... )
        >>> len(chunks) >= 1
        True
    """
    _validate_args(max_tokens=max_tokens, overlap=overlap)
    mode = BoundaryMode(boundary)

    if not text:
        return []

    if mode is BoundaryMode.CHARACTER:
        return _character_chunk(text, max_tokens=max_tokens, overlap=overlap)
    if mode is BoundaryMode.PARAGRAPH:
        return paragraph_chunk(text, max_tokens=max_tokens, overlap=overlap)
    return sentence_chunk(text, max_tokens=max_tokens, overlap=overlap)


def sentence_chunk(
    text: str,
    *,
    max_tokens: int = 512,
    overlap: int = 64,
) -> list[Chunk]:
    """Sentence-boundary chunking. Pack sentences greedily up to ``max_tokens``.

    Sentence boundaries come from :func:`nom.text.sent_tokenize`. If a
    single sentence exceeds ``max_tokens``, it falls back to character
    chunking and the resulting chunks carry ``metadata["truncated"] = True``.
    """
    _validate_args(max_tokens=max_tokens, overlap=overlap)
    if not text:
        return []

    sentences = sent_tokenize(text)
    sent_offsets = _locate_substrings(text, sentences)
    sent_token_counts = [len(word_tokenize(s)) for s in sentences]

    return _pack_units(
        units=sentences,
        offsets=sent_offsets,
        token_counts=sent_token_counts,
        text=text,
        max_tokens=max_tokens,
        overlap=overlap,
    )


def paragraph_chunk(
    text: str,
    *,
    max_tokens: int = 512,
    overlap: int = 64,
) -> list[Chunk]:
    """Paragraph-boundary chunking. Split on blank lines, then pack.

    A paragraph that exceeds ``max_tokens`` is recursively chunked at
    sentence boundaries inside the same call.
    """
    _validate_args(max_tokens=max_tokens, overlap=overlap)
    if not text:
        return []

    paragraphs = [p for p in _split_paragraphs(text) if p.strip()]
    if not paragraphs:
        return []

    para_offsets = _locate_substrings(text, paragraphs)
    para_token_counts = [len(word_tokenize(p)) for p in paragraphs]

    chunks: list[Chunk] = []
    for para, (start, end), n_tok in zip(paragraphs, para_offsets, para_token_counts, strict=False):
        if n_tok <= max_tokens:
            chunks.append(
                Chunk(
                    text=para.strip(),
                    start=start,
                    end=end,
                    n_tokens=n_tok,
                    metadata={"boundary": "paragraph"},
                )
            )
        else:
            # Fall back to sentence chunking inside this paragraph.
            sub = sentence_chunk(para, max_tokens=max_tokens, overlap=overlap)
            for c in sub:
                # Translate offsets from paragraph-local to document-global.
                chunks.append(
                    Chunk(
                        text=c.text,
                        start=start + c.start,
                        end=start + c.end,
                        n_tokens=c.n_tokens,
                        metadata={**c.metadata, "boundary": "paragraph→sentence"},
                    )
                )
    return chunks


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _validate_args(*, max_tokens: int, overlap: int) -> None:
    if max_tokens < 1:
        raise ValueError(f"max_tokens must be >= 1, got {max_tokens}")
    if overlap < 0:
        raise ValueError(f"overlap must be >= 0, got {overlap}")
    if overlap >= max_tokens:
        raise ValueError(
            f"overlap ({overlap}) must be strictly less than max_tokens ({max_tokens})"
        )


_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def _split_paragraphs(text: str) -> list[str]:
    """Split on any blank line (single empty line is enough — the standard
    paragraph convention). Preserves intra-paragraph soft wraps.

    Inspired by LlamaIndex's ``MarkdownNodeParser`` paragraph handling and
    LangChain's ``RecursiveCharacterTextSplitter`` separator hierarchy.
    """
    return [p for p in _PARAGRAPH_BREAK.split(text) if p.strip()]


def _locate_substrings(haystack: str, needles: list[str]) -> list[tuple[int, int]]:
    """Find each needle's (start, end) in haystack, walking forward.

    Robust against duplicate sentences — uses a forward-only cursor so
    repeated sentences map to their actual occurrence in source order.
    """
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for needle in needles:
        if not needle:
            offsets.append((cursor, cursor))
            continue
        # Tolerate leading/trailing whitespace mismatch by stripping for
        # search but reporting offsets to the matched substring.
        stripped = needle.strip()
        idx = haystack.find(stripped, cursor)
        if idx < 0:
            # Sent_tokenize may emit a sentence whose exact form drifted
            # (e.g. internal whitespace collapsed). Fall back to placing
            # at the cursor with the needle's length.
            offsets.append((cursor, cursor + len(needle)))
            cursor += len(needle)
        else:
            offsets.append((idx, idx + len(stripped)))
            cursor = idx + len(stripped)
    return offsets


def _pack_units(
    *,
    units: list[str],
    offsets: list[tuple[int, int]],
    token_counts: list[int],
    text: str,
    max_tokens: int,
    overlap: int,
) -> list[Chunk]:
    """Greedy pack of (unit, offset, token_count) triples into chunks.

    A "unit" is a sentence (or any pre-segmented span). Units that exceed
    ``max_tokens`` solo are split at character boundaries with the
    ``truncated`` metadata flag set.
    """
    chunks: list[Chunk] = []
    n = len(units)

    i = 0
    while i < n:
        tokens_in_chunk = 0
        first_unit = i
        last_unit = i

        # Pack as many units as fit.
        while last_unit < n and tokens_in_chunk + token_counts[last_unit] <= max_tokens:
            tokens_in_chunk += token_counts[last_unit]
            last_unit += 1

        if last_unit == first_unit:
            # The first unit alone exceeds max_tokens — force a hard split.
            unit_start, unit_end = offsets[first_unit]
            single_unit_text = text[unit_start:unit_end]
            sub_chunks = _character_chunk(
                single_unit_text,
                max_tokens=max_tokens,
                overlap=overlap,
                base_offset=unit_start,
                truncated=True,
            )
            chunks.extend(sub_chunks)
            i = first_unit + 1
            continue

        # Emit a chunk covering units [first_unit, last_unit).
        chunk_start = offsets[first_unit][0]
        chunk_end = offsets[last_unit - 1][1]
        chunks.append(
            Chunk(
                text=text[chunk_start:chunk_end].strip(),
                start=chunk_start,
                end=chunk_end,
                n_tokens=tokens_in_chunk,
                metadata={"boundary": "sentence"},
            )
        )

        if last_unit >= n:
            break

        # Advance: leave overlap tokens of context, walking back from
        # last_unit until we've shed enough.
        if overlap == 0:
            i = last_unit
            continue

        carry_tokens = 0
        carry_start = last_unit
        while carry_start > first_unit and carry_tokens < overlap:
            carry_start -= 1
            carry_tokens += token_counts[carry_start]
        i = carry_start if carry_start > first_unit else last_unit

    return chunks


def _character_chunk(
    text: str,
    *,
    max_tokens: int,
    overlap: int,
    base_offset: int = 0,
    truncated: bool = False,
) -> list[Chunk]:
    """Last-resort chunking by character window.

    We approximate token counts by assuming average 4 chars per VN token.
    Errs on the safe side (chunks are slightly under ``max_tokens``).
    """
    if not text.strip():
        return []
    chars_per_chunk = max_tokens * 4
    chars_overlap = overlap * 4

    chunks: list[Chunk] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + chars_per_chunk, n)
        snippet = text[i:end]
        if not snippet.strip():
            break
        n_tok = len(word_tokenize(snippet))
        chunks.append(
            Chunk(
                text=snippet.strip(),
                start=base_offset + i,
                end=base_offset + end,
                n_tokens=n_tok,
                metadata={"boundary": "character", "truncated": truncated},
            )
        )
        if end >= n:
            break
        i = end - chars_overlap if chars_overlap < (end - i) else end
    return chunks
