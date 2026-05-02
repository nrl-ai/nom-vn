"""Rule-based risk classifier — Đ9 / Đ10 / Đ11 / Đ14 / Đ15.

Inputs are a :class:`SystemSpec` describing the system. Output is a
:class:`ClassificationResult` carrying the tier, the reasoning chain,
and the article numbers that drove the decision. Every decision is
traceable; nothing is "the LLM said so."

The law itself is data — see :mod:`nom.compliance.laws`. The
classifier is generic over any :class:`LawSpec`. Adding a new
jurisdiction is one new ``laws/<id>.py`` plus a ``RiskClassifier(law=...)``
call; no changes to this module.

Why rules first (and rules-only at v0.3): for compliance, an
inspector wants to read the decision logic, not trust an opaque
model. A rule table is what a legal-tech reviewer can audit and
amend; an LLM tie-breaker for genuinely ambiguous cases is a v0.4
feature once the audit-log wrapper for that tie-breaker exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from nom.compliance.laws import LAW_VN_134_2025, LawSpec
from nom.compliance.types import RiskTier

__all__ = [
    "ClassificationResult",
    "RiskClassifier",
    "Sector",
    "SystemSpec",
]


# Sector literal stays narrow because every shipped law currently
# names the same five categories. When a future law introduces new
# sectors, broaden this and update the rules table accordingly.
Sector = Literal["health", "education", "finance", "public-services", "other"]

AutomationLevel = Literal["advisory", "semi-autonomous", "autonomous"]
"""How tightly the AI's output drives consequential action."""

UserScope = Literal["individual", "org", "public-mass"]
"""Who interacts with the system."""


@dataclass(frozen=True, slots=True)
class SystemSpec:
    """Inputs to the classifier — one frozen value per system.

    Don't synthesise a SystemSpec from a free-form description. Have
    the operator answer each field; the resulting record is what
    Đ10.1 calls the *hồ sơ phân loại* (classification dossier).
    """

    purpose: str
    sector: Sector
    automation_level: AutomationLevel
    user_scope: UserScope
    handles_personal_data: bool
    affects_vulnerable_groups: bool
    can_generate_synthetic_content: bool
    interacts_directly_with_users: bool = True


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Outcome of classification — tier + reasoning + article cites.

    ``law_id`` + ``law_version`` pin the LawSpec used at decision
    time so a reproduction years later can use the exact rule set
    that was applied.
    """

    tier: RiskTier
    applicable_articles: tuple[str, ...]
    reasoning: tuple[str, ...]
    fired_rule_ids: tuple[str, ...] = field(default_factory=tuple)
    law_id: str = ""
    law_version: str = ""


@dataclass
class RiskClassifier:
    """Deterministic LawSpec-driven classifier.

    Construct with ``law=LawSpec(...)`` to swap jurisdictions; the
    default points at the canonical Vietnam law. Custom rules fit
    by passing a derived ``LawSpec`` whose ``rules`` tuple has the
    overrides — keeps the law-as-data invariant intact.
    """

    law: LawSpec = field(default_factory=lambda: LAW_VN_134_2025)

    def classify(self, spec: SystemSpec) -> ClassificationResult:
        """Run every rule, take the highest tier any rule asserts."""
        fired = [r for r in self.law.rules if r.predicate(spec)]

        articles: list[str] = []
        if spec.interacts_directly_with_users:
            articles.extend(self.law.transparency_articles)
        if spec.can_generate_synthetic_content:
            articles.extend(("Đ11.2", "Đ11.4"))
        if spec.handles_personal_data and self.law.data_governance_article:
            articles.append(self.law.data_governance_article)

        if not fired:
            articles.extend(self.law.low_risk_obligations_articles)
            return ClassificationResult(
                tier=RiskTier.LOW,
                applicable_articles=_dedup(articles),
                reasoning=(
                    "Không rule nào leo thang tier; mặc định "
                    f"{self.law.risk_tier_articles[RiskTier.LOW]} "
                    "(rủi ro thấp).",
                ),
                fired_rule_ids=(),
                law_id=self.law.law_id,
                law_version=self.law.version,
            )

        ordering = {RiskTier.LOW: 0, RiskTier.MEDIUM: 1, RiskTier.HIGH: 2}
        winner = max(fired, key=lambda r: ordering[r.tier])

        for rule in fired:
            for art in rule.articles:
                articles.append(art)

        if winner.tier == RiskTier.HIGH:
            articles.extend(self.law.high_risk_obligations_articles)
        elif winner.tier == RiskTier.MEDIUM:
            articles.extend(self.law.medium_risk_obligations_articles)
        else:
            articles.extend(self.law.low_risk_obligations_articles)

        reasoning = tuple(f"[{r.rule_id}] {r.reason_vi}" for r in fired)
        return ClassificationResult(
            tier=winner.tier,
            applicable_articles=_dedup(articles),
            reasoning=reasoning,
            fired_rule_ids=tuple(r.rule_id for r in fired),
            law_id=self.law.law_id,
            law_version=self.law.version,
        )


def _dedup(items: list[str]) -> tuple[str, ...]:
    """Order-preserving dedup so article lists read top-down without
    repeats."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return tuple(out)
