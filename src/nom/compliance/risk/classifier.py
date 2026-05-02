"""Rule-based risk classifier — Đ9 / Đ10 / Đ11 / Đ14 / Đ15.

Inputs are a :class:`SystemSpec` describing the system. Output is a
:class:`ClassificationResult` carrying the tier, the reasoning chain,
and the article numbers that drove the decision. Every decision is
traceable; nothing is "the LLM said so."

Why rules first (and rules-only at v0.3): for compliance, an
inspector wants to read the decision logic, not trust an opaque
model. A rule table is what a legal-tech reviewer can audit and
amend; an LLM tie-breaker for genuinely ambiguous cases is a v0.4
feature once the audit-log wrapper for that tie-breaker exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from nom.compliance.risk.rules import RULE_TABLE, Rule
from nom.compliance.types import RiskTier

__all__ = [
    "ClassificationResult",
    "RiskClassifier",
    "Sector",
    "SystemSpec",
]


# Đ6.2 explicitly enumerates "lĩnh vực thiết yếu" (essential sectors)
# with healthcare and education called out by name; finance is the
# third sector with an extended grace period in Đ35. Public services
# and "other" round out the literal type so a SystemSpec never has to
# carry a free-form sector string.
Sector = Literal["health", "education", "finance", "public-services", "other"]

AutomationLevel = Literal["advisory", "semi-autonomous", "autonomous"]
"""How tightly the AI's output drives consequential action.

- ``advisory`` — output is a suggestion a human accepts/rejects.
- ``semi-autonomous`` — system acts on its output but a human is in
  the loop on every consequential step.
- ``autonomous`` — system acts without per-step human review.
"""

UserScope = Literal["individual", "org", "public-mass"]
"""Who interacts with the system.

- ``individual`` — single end user (personal assistant).
- ``org`` — internal organisation (employee tool, B2B SaaS).
- ``public-mass`` — open to the public at scale (consumer chatbot,
  public service).
"""


@dataclass(frozen=True, slots=True)
class SystemSpec:
    """Inputs to the classifier — one frozen value per system.

    Don't synthesise a SystemSpec from a free-form description. Have
    the operator answer each field; the resulting record is what
    Đ10.1 calls the *hồ sơ phân loại* (classification dossier).
    """

    purpose: str
    """One-line VN/EN description, e.g. "Trợ lý hỏi-đáp pháp luật"."""

    sector: Sector
    automation_level: AutomationLevel
    user_scope: UserScope

    handles_personal_data: bool
    """Triggers PDP Law obligations + Đ7.3 data-governance rules."""

    affects_vulnerable_groups: bool
    """Đ7.2.c — children, elderly, disabled, ethnic minorities, persons
    with limited mental capacity. Strong push toward HIGH."""

    can_generate_synthetic_content: bool
    """Triggers Đ11.2 machine-readable marking + Đ11.4 deepfake labeling."""

    interacts_directly_with_users: bool = True
    """Triggers Đ11.1 "you are talking to AI" disclosure when True."""


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Outcome of classification — tier + reasoning + article cites.

    ``applicable_articles`` is the list an inspector reads first; it
    tells them which obligations (Đ11/Đ12/Đ14/Đ15) you've signed up
    to. ``reasoning`` walks through the rules that fired so a legal
    reviewer can sanity-check the call.
    """

    tier: RiskTier
    applicable_articles: tuple[str, ...]
    reasoning: tuple[str, ...]
    fired_rule_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class RiskClassifier:
    """Deterministic rule-table classifier.

    Pass a custom ``rules`` list to override the default — useful for
    sectors with tighter internal policy (e.g., a bank that wants any
    customer-facing AI auto-classified HIGH regardless of scope).
    """

    rules: tuple[Rule, ...] = field(default_factory=lambda: tuple(RULE_TABLE))
    law: Literal["VN-134/2025"] = "VN-134/2025"

    def classify(self, spec: SystemSpec) -> ClassificationResult:
        """Run every rule, take the highest tier any rule asserts.

        Reasoning collects every fired rule's explanation so the audit
        trail records *why* HIGH (vs. just "HIGH"). If no rule fires
        the system is LOW with the explicit "no escalating rule
        matched" reasoning — never silently HIGH.
        """
        fired: list[Rule] = [r for r in self.rules if r.matches(spec)]

        # Always-applicable transparency / interaction articles.
        articles: list[str] = []
        if spec.interacts_directly_with_users:
            articles.append("Đ11.1")
        if spec.can_generate_synthetic_content:
            articles.extend(["Đ11.2", "Đ11.4"])
        if spec.handles_personal_data:
            articles.append("Đ7.3")

        if not fired:
            articles.extend(["Đ9.1.c", "Đ15.2"])
            return ClassificationResult(
                tier=RiskTier.LOW,
                applicable_articles=_dedup(articles),
                reasoning=("Không rule nào leo thang tier; mặc định Đ9.1.c (rủi ro thấp).",),
                fired_rule_ids=(),
            )

        # Highest tier wins (HIGH > MEDIUM > LOW).
        ordering = {RiskTier.LOW: 0, RiskTier.MEDIUM: 1, RiskTier.HIGH: 2}
        winner = max(fired, key=lambda r: ordering[r.tier])

        for rule in fired:
            for art in rule.articles:
                articles.append(art)

        # Tier-specific obligations (Đ14 high, Đ15.1 medium, Đ15.2 low).
        if winner.tier == RiskTier.HIGH:
            articles.extend(["Đ9.1.a", "Đ10.3", "Đ13", "Đ14.1"])
        elif winner.tier == RiskTier.MEDIUM:
            articles.extend(["Đ9.1.b", "Đ10.3", "Đ15.1"])
        else:
            articles.extend(["Đ9.1.c", "Đ15.2"])

        reasoning = tuple(f"[{r.rule_id}] {r.reason}" for r in fired)
        return ClassificationResult(
            tier=winner.tier,
            applicable_articles=_dedup(articles),
            reasoning=reasoning,
            fired_rule_ids=tuple(r.rule_id for r in fired),
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
