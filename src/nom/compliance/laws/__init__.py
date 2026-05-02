"""Laws as versioned data — pluggable per jurisdiction.

The risk classifier and dossier generators don't hard-code "Vietnam Law
134/2025". They consume a :class:`LawSpec` value that carries the law
identifier, version, articles, risk tiers, sectors, and a typed list
of :class:`RuleSpec` predicates.

Adding a new law (EU AI Act, Singapore, etc.) is one new module that
constructs and exports a :class:`LawSpec` constant. Updating an
existing law for a new implementing decree is a new module / new
version of the law constant — readers / verifiers can pin a specific
version when reproducing classifications years later.

Versioning convention: filename is ``<jurisdiction>_<id>.py``; the
module exports ``LAW: LawSpec`` with ``law_id`` (stable jurisdiction
identifier) and ``version`` (semver, bumped on substantive change).
A registry helper :func:`get` resolves by ``law_id`` to the
currently-recommended version; pin explicitly via direct module
import for deterministic reproduction.
"""

from __future__ import annotations

from nom.compliance.laws._types import (
    LawSpec,
    PendingDecree,
    RuleSpec,
    SectorSpec,
)
from nom.compliance.laws.registry import available, get
from nom.compliance.laws.vn_134_2025 import LAW as VN_134_2025

__all__ = [
    "LAW_VN_134_2025",
    "LawSpec",
    "PendingDecree",
    "RuleSpec",
    "SectorSpec",
    "available",
    "get",
]


# Friendly alias matching the law's everyday name.
LAW_VN_134_2025 = VN_134_2025
