"""Vietnamese text utilities.

The module ships in v0.0.1. All functions are pure-Python, no external models.
"""

from nom.text.normalize import (
    fix_diacritics,
    has_diacritics,
    is_vietnamese,
    normalize,
    strip_diacritics,
)

__all__ = [
    "fix_diacritics",
    "has_diacritics",
    "is_vietnamese",
    "normalize",
    "strip_diacritics",
]
