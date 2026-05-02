"""Risk classification per Luật 134/2025/QH15 Đ9 + Đ10.

Đ9.1 names three tiers:

- ``HIGH`` (Đ9.1.a) — significant harm to life, health, rights,
  national interests, public interests, or national security.
- ``MEDIUM`` (Đ9.1.b) — risk of confusion or manipulation when users
  cannot recognize they are interacting with AI or with AI-generated
  content.
- ``LOW`` (Đ9.1.c) — everything not in the two above.

Đ9.2 lists the criteria a classifier must consider: impact on human
rights / safety / security, sector of use (especially essential
sectors per Đ6.2), user scope, and scale of influence. Đ7 lists
prohibited uses including those targeting vulnerable groups
(children, the elderly, disabled, ethnic minorities, persons with
limited mental capacity).

Đ10.1 puts classification on the provider before deployment.
:class:`RiskClassifier` is the deterministic, audit-friendly entry
point. Output cites the articles that applied so the result reads as
a defensible self-classification dossier (Đ10.3).

A future LLM tie-breaker for ambiguous cases lands in v0.4 once
:mod:`nom.compliance.wrappers` is in place to audit-log the
tie-breaker call itself.
"""

from __future__ import annotations

from nom.compliance.risk.classifier import (
    ClassificationResult,
    RiskClassifier,
    SystemSpec,
)

__all__ = [
    "ClassificationResult",
    "RiskClassifier",
    "SystemSpec",
]
