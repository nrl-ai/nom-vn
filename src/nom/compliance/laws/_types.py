"""Typed value classes for a law specification.

A law is data, not code — the only Python that lives next to the
data is the predicate lambda for each rule (kept typed and
auditable). Everything else (article numbers, sector descriptions,
tier definitions, deadlines, pending decrees) is plain values.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nom.compliance.types import RiskTier

if TYPE_CHECKING:
    from nom.compliance.risk.classifier import SystemSpec

__all__ = [
    "LawSpec",
    "PendingDecree",
    "RuleSpec",
    "SectorSpec",
]


@dataclass(frozen=True, slots=True)
class SectorSpec:
    """One sector named or implied by the law.

    The classifier matches ``SystemSpec.sector`` against ``id``;
    citations push ``articles`` into the result.
    """

    id: str
    """Stable identifier matching ``SystemSpec.sector`` literal."""

    title_vi: str
    title_en: str
    articles: tuple[str, ...] = ()
    """Articles where this sector is named (e.g. Đ6.2.a for health)."""

    is_essential: bool = False
    """Sectors flagged "thiết yếu" per Đ6.2 or equivalent."""


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """One classifier rule in the law.

    The predicate lives next to the data — typed, auditable, and not
    parsed from strings (no eval surface).
    """

    rule_id: str
    """Unique identifier — fires through to ClassificationResult."""

    tier: RiskTier
    articles: tuple[str, ...]
    reason_vi: str
    predicate: Callable[[SystemSpec], bool]


@dataclass(frozen=True, slots=True)
class PendingDecree:
    """A decree / implementing regulation the law defers to.

    ``article`` is the law's reference (e.g. "Đ13.4"); ``topic_vi``
    is a one-line description used in the docs / UI; ``status_note``
    flags whether the module ships a placeholder today
    ("MVP skeleton" / "deferred to v0.4" etc.).
    """

    article: str
    topic_vi: str
    status_note: str = ""


@dataclass(frozen=True, slots=True)
class LawSpec:
    """Complete specification of one law / version.

    Stable across implementing-decree updates: when a decree changes
    a rule's interpretation, ship a new module ``<id>_v<n>.py`` that
    exports a new ``LawSpec`` with bumped ``version``. Old code
    pinning the previous module keeps working; new callers get the
    new behaviour.
    """

    law_id: str
    """Jurisdiction-stable identifier, e.g. "VN-134/2025"."""

    version: str
    """Semantic version of this LawSpec — bump on substantive change."""

    title_vi: str
    title_en: str
    issued_date: str
    """ISO-8601 of the date the law was passed."""

    effective_date: str
    """ISO-8601 of the effective date."""

    authority: str
    """Issuing body, e.g. "Quốc hội nước CHXHCN Việt Nam khóa XV"."""

    risk_tier_articles: dict[RiskTier, str] = field(default_factory=dict)
    """Map RiskTier → article number where the tier is defined.
    E.g. {HIGH: "Đ9.1.a", MEDIUM: "Đ9.1.b", LOW: "Đ9.1.c"} for VN-134."""

    sectors: tuple[SectorSpec, ...] = ()
    rules: tuple[RuleSpec, ...] = ()

    deadlines: dict[str, str] = field(default_factory=dict)
    """Free-form deadline map. Conventions:
    - ``"effective"`` — universal effective date
    - ``"general"`` — generic transition deadline
    - ``"<sector_id>"`` — sector-specific deadline if different"""

    pending_decrees: tuple[PendingDecree, ...] = ()

    transparency_articles: tuple[str, ...] = ()
    """Article numbers attached when the system interacts directly with
    users or generates synthetic content."""

    data_governance_article: str = ""
    """Article forbidding unlawful data-handling (e.g. Đ7.3 for VN)."""

    high_risk_obligations_articles: tuple[str, ...] = ()
    """Articles auto-attached when the classifier returns HIGH."""

    medium_risk_obligations_articles: tuple[str, ...] = ()
    low_risk_obligations_articles: tuple[str, ...] = ()
