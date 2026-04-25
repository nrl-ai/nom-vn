"""Vietnamese text utilities.

Two layers:

- **Zero-dependency** (always available): :func:`normalize`, :func:`strip_diacritics`,
  :func:`has_diacritics`, :func:`is_vietnamese`, :func:`fix_diacritics`.
- **NLP-backed** (requires ``pip install nom-vn[nlp]``): word/sentence
  tokenization and VN-aware text normalization. See ``nom.text.segment``.
"""

from nom.text.normalize import (
    fix_diacritics,
    has_diacritics,
    is_vietnamese,
    normalize,
    strip_diacritics,
)
from nom.text.segment import sent_tokenize, text_normalize, word_tokenize

__all__ = [
    "fix_diacritics",
    "has_diacritics",
    "is_vietnamese",
    "normalize",
    "sent_tokenize",
    "strip_diacritics",
    "text_normalize",
    "word_tokenize",
]
