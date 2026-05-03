"""VN legal-domain NER patterns — LAW_REF, ID_NUMBER_VN, PHONE_VN, etc.

Companion to :mod:`nom.nlp.ner` for the compliance / legal use case.
The 4 standard NER labels (PER / ORG / LOC / MISC) plus DATE / MONEY
that the base regex / PhoBERT NER covers don't catch the entities a
legal-document workflow actually needs:

- ``LAW_REF`` — references to Vietnamese laws, decrees, circulars,
  and law articles. Patterns picked from the survey of public legal
  corpora (Zalo Legal QA, th1nhng0/vietnamese-legal-documents):

  * ``Luật <Name>`` / ``Luật số <NN>/<YYYY>/QH<N>``
  * ``Nghị định <NN>/<YYYY>/NĐ-CP``
  * ``Thông tư <NN>/<YYYY>/TT-B<x>``
  * ``Điều <N>`` / ``Điều <N> Luật ...``
  * ``Khoản <N>`` / ``Điểm <a>`` (sub-clause references)

- ``ID_VN`` — 9-digit (legacy CMND) or 12-digit (CCCD) Vietnamese
  national ID numbers. Looks for digits in those exact widths surrounded
  by word boundaries to avoid catching random invoice numbers.

- ``PHONE_VN`` — VN phone-number formats: ``0xx xxx xxxx`` /
  ``+84 xx xxx xxxx`` / ``(0xx) xxx xxxx``.

This is the *cheap* path to legal entity coverage — pure regex, no
training, deterministic, NFC-safe. The full ML path (PhoBERT-base
fine-tuned on a corpus with manual LAW_REF / CONTRACT_PARTY annotations)
is Tier 3 work per ``docs/sota_vn_2026q2_expansion.md`` — gated on the
70-90 hr annotation budget.

Compose with the base regex NER:

>>> from nom.nlp.ner import RegexNERModel
>>> from nom.nlp.ner_legal import legal_ner_patterns
>>> ner = RegexNERModel(extra_patterns=legal_ner_patterns())
>>> ner.tag("Theo Điều 5 Luật 134/2025/QH15, ID 012345678901 ...")
"""

from __future__ import annotations

__all__ = ["legal_ner_patterns"]


def legal_ner_patterns() -> tuple[tuple[str, str], ...]:
    """Return the legal-domain regex pattern set as ``(label, pattern)``
    pairs ready to drop into ``RegexNERModel(extra_patterns=...)``.
    """
    return (
        # Law references: ``Luật ...``, ``Nghị định N/YYYY/NĐ-CP``,
        # ``Thông tư N/YYYY/TT-B*``, ``Quyết định N/YYYY/...``.
        # Order matters — most specific first so longer-span wins in the
        # RegexNERModel overlap resolution.
        (
            "LAW_REF",
            r"\b(?:Nghị\s+định|Thông\s+tư|Quyết\s+định|Luật|Bộ\s+luật|"
            r"Pháp\s+lệnh|Hiến\s+pháp)\s+(?:số\s+)?\d+(?:[-/]\d+)+(?:/[A-Z0-9Đ\-]+)*",
        ),
        # Bare law family + number when only 1 number ("Luật 134/2025"
        # without the QH suffix). Matches the Toshiiiii1 / VnExpress style.
        (
            "LAW_REF",
            r"\b(?:Nghị\s+định|Thông\s+tư|Quyết\s+định|Luật|Bộ\s+luật)\s+"
            r"(?:số\s+)?\d+/\d{4}\b",
        ),
        # Article references: ``Điều 5``, ``Điều 5 Luật ...``,
        # ``Khoản 2 Điều 5``, ``Điểm a Khoản 1``.
        (
            "LAW_REF",
            r"\b(?:Điều|Khoản|Điểm)\s+\d+[a-z]?(?:\s+[A-Za-zÀ-ỹ])*",
        ),
        # CMND (9 digits) / CCCD (12 digits) — strict word boundaries to
        # avoid invoice numbers, order IDs, etc.
        ("ID_VN", r"(?<!\d)\d{12}(?!\d)"),
        ("ID_VN", r"(?<!\d)\d{9}(?!\d)"),
        # VN phones: 10-11 digits with leading 0 or +84. Real VN numbers
        # come in two grouping styles: 4-3-3 (mobile) and 2-4-4 (landline
        # / hotline). Accept both with optional separators (space / dot
        # / hyphen) — total digit count after stripping is 9-11, which
        # covers every legitimate VN phone format.
        (
            "PHONE_VN",
            r"\+84[\s.-]?\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{3,4}",
        ),
        (
            "PHONE_VN",
            r"\b0\d{2,3}[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b",
        ),
    )
