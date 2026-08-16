"""Heading-shaped input detection and conservative tone-only edit merging.

Our seq2seq spell-correction models are trained on sentence-segmented text.
Document furniture (letterheads, all-caps titles, form labels, signature
blocks) was filtered out during corpus construction, so the models carry no
correction prior for that surface form and silently echo it back.

The failure needs two conditions at once:

1. an adverse frequency prior, where the typo is a valid syllable that is
   more common in the corpus than the intended word, and
2. heading-shaped layout the encoder has effectively never seen corrected.

Neither alone is enough. ``Tôi rất hạnh phục khi gặp lại bạn`` is corrected;
``Độc lập - Tự do - Hạnh phục`` is not, despite carrying the same error.

Correcting a lowercased copy and re-applying the original casing recovers
these cases, because lowercase running text is in-distribution. Doing that
unconditionally is unsafe: it rewrites acronyms (``QĐ-UBND`` becomes
``QĐ-BND``) and wrecks undiacritized input (``Toi yu Vit Nam`` becomes
``Tội tử Vì Nam``). :func:`merge_tone_only` is the guard that makes the
retry safe, accepting only tone-level edits on purely alphabetic tokens.

Example::

    >>> is_heading("Độc lập - Tự do - Hạnh phục")
    True
    >>> is_heading("Tôi rất hạnh phục khi gặp lại bạn.")
    False
    >>> merge_tone_only("ĐƠN XIN NGHĨ VIỆC", "đơn xin nghỉ việc")
    'ĐƠN XIN NGHỈ VIỆC'
    >>> merge_tone_only("Số: 15/QĐ-UBND", "số: 15/qđ-bnd")
    'Số: 15/QĐ-UBND'
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["is_heading", "merge_tone_only"]

# Combining tone marks: huyền, sắc, ngã, hỏi, nặng. Vowel modifiers
# (â ê ô ơ ư ă) and đ are deliberately excluded -- changing those is a
# letter-level edit, not a tone edit, and must not pass the guard.
_TONE_MARKS = frozenset("̣̀́̃̉")

# A token is "purely alphabetic" when it has no digits, underscores, or
# punctuation. This is what keeps codes like `15/QĐ-UBND` out of the merge.
_ALPHA_TOKEN = re.compile(r"^[^\W\d_]+$", re.UNICODE)

# Token spans, so the merge can splice corrections back into the source and
# leave every original separator byte-for-byte intact. Rebuilding with
# `" ".join(...)` instead would silently flatten newlines, tabs and repeated
# spaces, which matters for letterhead blocks that carry real line structure.
_TOKEN_SPAN = re.compile(r"\S+")

_MAX_HEADING_TOKENS = 12
_MIN_CAPITALIZED_RATIO = 0.5


def _detone(word: str) -> str:
    """Strip tone marks only, preserving vowel modifiers and ``đ``."""
    decomposed = unicodedata.normalize("NFD", word)
    return unicodedata.normalize("NFC", "".join(c for c in decomposed if c not in _TONE_MARKS))


def is_heading(text: str) -> bool:
    """Return True when ``text`` looks like document furniture, not a sentence.

    Heading-shaped means short, without sentence-final punctuation, and
    either fully upper-case or at least half title-cased across its
    alphabetic tokens.

    Example:
        >>> is_heading("GIẤY CHỨNG NHẬN ĐĂNG KÝ KINH DOANH")
        True
        >>> is_heading("Kính gửi: Ban Giám đốc Công ty")
        True
        >>> is_heading("hôm nay trời đẹp quá")
        False
    """
    stripped = text.strip()
    if not stripped:
        return False
    tokens = stripped.split()
    if len(tokens) > _MAX_HEADING_TOKENS:
        return False
    if stripped.endswith((".", "!", "?")):
        return False
    alpha = [t for t in tokens if _ALPHA_TOKEN.match(t)]
    if not alpha:
        return False
    if all(t.isupper() for t in alpha):
        return True
    capitalized = sum(1 for t in alpha if t[:1].isupper())
    return capitalized / len(alpha) >= _MIN_CAPITALIZED_RATIO


def merge_tone_only(source: str, candidate: str) -> str:
    """Take from ``candidate`` only its tone-level edits on alphabetic tokens.

    Every other difference is discarded in favour of ``source``, and the
    original casing of each accepted token is restored. When the two strings
    disagree on token count the merge is abandoned and ``source`` is returned
    unchanged, since positional alignment is no longer meaningful.

    Args:
        source: the original text, whose casing and structure win.
        candidate: a corrected variant, typically produced by running the
            model over ``source.lower()``.

    Whitespace comes from ``source`` untouched, including newlines, tabs and
    repeated spaces.

    Returns:
        ``source`` with tone-level corrections applied, NFC-normalized.

    Example:
        >>> merge_tone_only("Hạnh phục", "hạnh phúc")
        'Hạnh phúc'
        >>> merge_tone_only("Toi yu Vit Nam", "tôi yêu việt nam")
        'Toi yu Vit Nam'
        >>> merge_tone_only("QUYẾT ĐỊNH\\nVề việc bổ nhiêm", "quyết định\\nvề việc bổ nhiệm")
        'QUYẾT ĐỊNH\\nVề việc bổ nhiệm'
    """
    src_spans = list(_TOKEN_SPAN.finditer(source))
    cand_tokens = candidate.split()
    if len(src_spans) != len(cand_tokens):
        return source

    merged: list[str] = []
    cursor = 0
    for span, cand in zip(src_spans, cand_tokens, strict=True):
        merged.append(source[cursor : span.start()])
        src = span.group()
        cursor = span.end()
        if src == cand:
            merged.append(src)
            continue
        if not (_ALPHA_TOKEN.match(src) and _ALPHA_TOKEN.match(cand)):
            merged.append(src)
            continue
        if src.lower() == cand.lower():
            # Differs by case alone, so there is no tone edit to take. Round
            # -tripping through _restore_case here would corrupt mixed-case
            # acronyms: `PTTgTT` came back as `Pttgtt`.
            merged.append(src)
            continue
        if _detone(src.lower()) != _detone(cand.lower()):
            merged.append(src)
            continue
        merged.append(_restore_case(src, cand))
    merged.append(source[cursor:])
    return unicodedata.normalize("NFC", "".join(merged))


def _restore_case(source: str, candidate: str) -> str:
    """Re-apply ``source``'s casing pattern to ``candidate``.

    Prefers a per-character copy, which is exact for Vietnamese tone edits
    because swapping a tone preserves length in NFC. That keeps interior
    capitals in mixed-case tokens intact; title-casing the whole token would
    turn ``PTTgTT`` into ``Pttgtt``.
    """
    if source.isupper() and len(source) > 1:
        return candidate.upper()
    if len(source) == len(candidate):
        return "".join(
            c.upper() if s.isupper() else c.lower() for s, c in zip(source, candidate, strict=True)
        )
    if source[:1].isupper():
        return candidate[:1].upper() + candidate[1:]
    return candidate
