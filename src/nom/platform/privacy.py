"""``PIIDetector`` + ``Redactor`` Protocols, with VN-aware OSS defaults.

The OSS default ``RegexPIIDetector`` ships patterns for the most
common Vietnamese-context PII types — basic but covers the main
Nghị định 13/2023 categories. Production deployments swap in
``nom_ee.privacy`` for VN NER (person names, addresses) and tokenize
policies that round-trip via a stored mapping table.

Policy semantics (shared by OSS and EE redactors so workspaces can
move between tiers without rule rewrites):

- ``"mask"`` — replace with a typed placeholder (``[CCCD]``, ``[EMAIL]``)
- ``"hash"`` — replace with deterministic short hash
  (``[email:8a3f]``); same input gives same output, so joins still work
- ``"drop"`` — remove the span entirely

The detector scans linearly; output spans are non-overlapping and
sorted by start offset. When two patterns hit the same range, the
higher-priority one (CCCD > MST > generic-number) wins.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

__all__ = [
    "MaskRedactor",
    "PIIDetector",
    "PIISpan",
    "Redactor",
    "RegexPIIDetector",
]


@dataclass(frozen=True, slots=True)
class PIISpan:
    """A detected PII region in some input text.

    Coordinates are Python string slice indices on the *original*
    text (post-NFC). ``kind`` is a stable string identifier — the
    redactor uses it to pick the placeholder, and the audit log
    can record category-level statistics without storing raw values.
    """

    start: int
    end: int
    kind: str
    value: str
    confidence: float = 1.0


@runtime_checkable
class PIIDetector(Protocol):
    name: str

    def detect(self, text: str) -> tuple[PIISpan, ...]:
        """Return all PII spans in text, non-overlapping, sorted by start."""
        ...


@runtime_checkable
class Redactor(Protocol):
    name: str

    def redact(
        self,
        text: str,
        spans: tuple[PIISpan, ...],
        *,
        policy: str = "mask",
    ) -> str:
        """Return text with each span replaced per ``policy``."""
        ...


# Patterns ordered by priority — first match wins on overlap.
# Each entry: (kind, regex, priority). Higher priority = earlier.
#
# Anchors and boundaries:
# - VN identifiers (CCCD, CMND, MST, STK) use \b on both sides so they
#   don't false-match inside longer digit runs.
# - Phone numbers handle both +84 and 0-prefixed forms.
# - CCCD (12 digits) checked before CMND (9) before generic digit runs.
# - Phone outranks MST: a 10-digit run with a valid VN mobile prefix
#   (091…, 098…, +84…) is more specifically a phone than an MST. The
#   alternative — letting MST win on bare 10-digit runs — silently
#   misses every mobile number that doesn't appear next to a tax-ID
#   keyword. The tradeoff: a real 10-digit MST whose first 3 digits
#   coincide with a VN mobile prefix gets tagged ``phone_vn``. In
#   practice MSTs are written with a branch suffix or in MST contexts,
#   so this is the right default for unconstrained text.
_DEFAULT_PATTERNS: tuple[tuple[str, str, int], ...] = (
    ("cccd", r"\b\d{12}\b", 100),
    (
        "phone_vn",
        r"(?:\+84|0)(?:3[2-9]|5[2689]|7[06-9]|8[1-689]|9[0-46-9])\d{7}\b",
        95,
    ),
    ("cmnd", r"\b\d{9}\b", 90),
    ("mst", r"\b\d{10}(?:-\d{3})?\b", 85),
    ("stk_vn", r"\b\d{8,16}\b", 70),
    ("email", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", 60),
)


@dataclass
class RegexPIIDetector:
    """OSS default: regex over VN-context PII categories.

    Built-in coverage:

    - **CCCD** (Căn cước công dân, 12 digits) — highest priority
    - **CMND** (Chứng minh nhân dân, 9 digits)
    - **MST** (Mã số thuế, 10 or 13 digits w/ branch)
    - **Phone (VN)** — `+84` and `0`-prefixed mobile prefixes only;
      landline 02x is intentionally excluded to avoid hitting random
      10-digit numbers
    - **STK ngân hàng** (8-16 digits, lowest priority — many
      false positives)
    - **Email**

    Production deployments add VN NER (person names, addresses) via
    the EE plugin. The regex set here is good enough for compliance
    sanity checks but should not be the last line of defence.
    """

    patterns: tuple[tuple[str, str, int], ...] = field(default_factory=lambda: _DEFAULT_PATTERNS)
    name: str = "regex"

    def __post_init__(self) -> None:
        self._compiled: list[tuple[str, re.Pattern[str], int]] = [
            (kind, re.compile(pattern), priority) for kind, pattern, priority in self.patterns
        ]

    def detect(self, text: str) -> tuple[PIISpan, ...]:
        # Collect all matches across patterns
        candidates: list[tuple[int, int, str, str, int]] = []
        for kind, regex, priority in self._compiled:
            for m in regex.finditer(text):
                candidates.append((m.start(), m.end(), kind, m.group(0), priority))

        # Resolve overlaps: highest priority wins; on tie, longest span
        candidates.sort(key=lambda c: (-c[4], -(c[1] - c[0]), c[0]))

        kept: list[tuple[int, int, str, str, int]] = []
        for cand in candidates:
            start, end, _, _, _ = cand
            if any(not (end <= ks or start >= ke) for ks, ke, *_ in kept):
                continue
            kept.append(cand)

        kept.sort(key=lambda c: c[0])
        return tuple(PIISpan(start=s, end=e, kind=k, value=v) for s, e, k, v, _ in kept)


@dataclass
class MaskRedactor:
    """OSS default redactor implementing mask / hash / drop policies.

    The output preserves text length only for ``"mask"`` when the
    placeholder happens to fit; callers shouldn't depend on offset
    stability across redaction.
    """

    hash_secret: bytes = b""
    name: str = "mask"

    def redact(
        self,
        text: str,
        spans: tuple[PIISpan, ...],
        *,
        policy: str = "mask",
    ) -> str:
        if not spans:
            return text
        if policy not in {"mask", "hash", "drop"}:
            msg = f"unknown redact policy: {policy!r}"
            raise ValueError(msg)

        # Apply right-to-left so earlier offsets remain valid.
        out = text
        for span in sorted(spans, key=lambda s: s.start, reverse=True):
            replacement = self._replacement(span, policy)
            out = out[: span.start] + replacement + out[span.end :]
        return out

    def _replacement(self, span: PIISpan, policy: str) -> str:
        if policy == "drop":
            return ""
        if policy == "mask":
            return f"[{span.kind.upper()}]"
        # policy == "hash"
        h = hashlib.sha256(self.hash_secret + span.value.encode("utf-8")).hexdigest()
        return f"[{span.kind}:{h[:8]}]"
