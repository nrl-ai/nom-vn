"""Dossier generators — Đ10, Đ13, Đ14.1.c, Đ27.

Four artifacts a high-risk system provider eventually hands to Bộ
KH&CN or to a registered conformity-assessment organisation:

- :class:`ClassificationDossier` (Đ10) — accompanies the
  pre-deployment notification. Full implementation; renders the
  classification result + system spec into a notification-ready
  package.
- :class:`TechnicalDossier` (Đ14.1.c) — the *hồ sơ kỹ thuật*. Full
  implementation; reads from a running pipeline + audit log to
  produce a marked-up report covering risk management, data
  governance, human oversight, transparency artifacts, and an
  operational-log summary.
- :class:`ConformityPackage` (Đ13) — MVP skeleton. The PM's mandatory
  certification list (Đ13.4) hasn't published yet; the skeleton
  emits a structurally complete document with placeholder fields
  useful for self-assessment per Đ25.1.
- :class:`ImpactAssessment` (Đ27) — MVP skeleton for state-use AI;
  full template lands when Đ27.5 implementing regulation publishes.
"""

from __future__ import annotations

from nom.compliance.dossier.classification import ClassificationDossier
from nom.compliance.dossier.conformity import ConformityPackage
from nom.compliance.dossier.impact import ImpactAssessment
from nom.compliance.dossier.technical import TechnicalDossier

__all__ = [
    "ClassificationDossier",
    "ConformityPackage",
    "ImpactAssessment",
    "TechnicalDossier",
]
