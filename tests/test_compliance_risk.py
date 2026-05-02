"""Tests for ``nom.compliance.risk`` — rule coverage + tier ordering.

Coverage strategy: hand-curated SystemSpec inputs across every named
sector x automation level x user scope combination that the rule
table mentions. Each test asserts (a) the expected tier, (b) the
expected article citations, and (c) which rule_id fired — so a future
table edit that silently swallows a case is caught.
"""

from __future__ import annotations

import pytest

from nom.compliance import RiskTier
from nom.compliance.risk import ClassificationResult, RiskClassifier, SystemSpec

# ---------------------------------------------------------------------------
# fixtures — pre-baked specs we mutate per test
# ---------------------------------------------------------------------------


def base_spec(**overrides: object) -> SystemSpec:
    """A neutral LOW-tier baseline; tests override one field at a time."""
    defaults: dict[str, object] = {
        "purpose": "Internal note-taking assistant",
        "sector": "other",
        "automation_level": "advisory",
        "user_scope": "individual",
        "handles_personal_data": False,
        "affects_vulnerable_groups": False,
        "can_generate_synthetic_content": False,
        "interacts_directly_with_users": True,
    }
    defaults.update(overrides)
    return SystemSpec(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def classifier() -> RiskClassifier:
    return RiskClassifier()


# ---------------------------------------------------------------------------
# LOW — no rule fires
# ---------------------------------------------------------------------------


def test_baseline_low_tier(classifier: RiskClassifier) -> None:
    result = classifier.classify(base_spec())
    assert result.tier is RiskTier.LOW
    assert result.fired_rule_ids == ()
    assert "Đ9.1.c" in result.applicable_articles
    assert "Đ15.2" in result.applicable_articles


def test_low_tier_still_includes_transparency(classifier: RiskClassifier) -> None:
    """interacts_directly_with_users=True always brings Đ11.1 in."""
    result = classifier.classify(base_spec())
    assert "Đ11.1" in result.applicable_articles


def test_personal_data_adds_data_governance(classifier: RiskClassifier) -> None:
    result = classifier.classify(base_spec(handles_personal_data=True))
    assert "Đ7.3" in result.applicable_articles


# ---------------------------------------------------------------------------
# Đ7.2.c — vulnerable groups → HIGH
# ---------------------------------------------------------------------------


def test_vulnerable_groups_forces_high(classifier: RiskClassifier) -> None:
    result = classifier.classify(base_spec(affects_vulnerable_groups=True))
    assert result.tier is RiskTier.HIGH
    assert "VN-134.7.2c.vulnerable" in result.fired_rule_ids
    assert "Đ7.2.c" in result.applicable_articles
    assert "Đ14.1" in result.applicable_articles


# ---------------------------------------------------------------------------
# Đ6.2.a healthcare
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["semi-autonomous", "autonomous"])
def test_healthcare_non_advisory_high(classifier: RiskClassifier, level: str) -> None:
    result = classifier.classify(base_spec(sector="health", automation_level=level))
    assert result.tier is RiskTier.HIGH
    assert "VN-134.6.2a.health.non_advisory" in result.fired_rule_ids
    assert "Đ6.2.a" in result.applicable_articles


def test_healthcare_advisory_medium(classifier: RiskClassifier) -> None:
    result = classifier.classify(base_spec(sector="health", automation_level="advisory"))
    assert result.tier is RiskTier.MEDIUM
    assert "VN-134.6.2a.health.advisory" in result.fired_rule_ids
    assert "Đ11" in result.applicable_articles


# ---------------------------------------------------------------------------
# Đ6.2.b education
# ---------------------------------------------------------------------------


def test_education_autonomous_high(classifier: RiskClassifier) -> None:
    result = classifier.classify(base_spec(sector="education", automation_level="autonomous"))
    assert result.tier is RiskTier.HIGH
    assert "VN-134.6.2b.education.non_advisory" in result.fired_rule_ids


def test_education_advisory_low(classifier: RiskClassifier) -> None:
    result = classifier.classify(base_spec(sector="education", automation_level="advisory"))
    assert result.tier is RiskTier.LOW


# ---------------------------------------------------------------------------
# Finance — Đ35.1.a 18-month grace
# ---------------------------------------------------------------------------


def test_finance_autonomous_high(classifier: RiskClassifier) -> None:
    result = classifier.classify(
        base_spec(sector="finance", automation_level="semi-autonomous", user_scope="org")
    )
    assert result.tier is RiskTier.HIGH
    assert "VN-134.35.1a.finance.non_advisory" in result.fired_rule_ids
    assert "Đ35.1.a" in result.applicable_articles


# ---------------------------------------------------------------------------
# Đ27 public services
# ---------------------------------------------------------------------------


def test_public_services_autonomous_public_mass_high(classifier: RiskClassifier) -> None:
    result = classifier.classify(
        base_spec(
            sector="public-services",
            automation_level="autonomous",
            user_scope="public-mass",
        )
    )
    assert result.tier is RiskTier.HIGH
    assert "VN-134.27.public_services.autonomous" in result.fired_rule_ids
    assert "Đ27.3" in result.applicable_articles


def test_public_services_advisory_low(classifier: RiskClassifier) -> None:
    result = classifier.classify(
        base_spec(
            sector="public-services",
            automation_level="advisory",
            user_scope="org",
        )
    )
    assert result.tier is RiskTier.LOW


# ---------------------------------------------------------------------------
# Đ11 transparency — synthetic content
# ---------------------------------------------------------------------------


def test_synthetic_content_internal_medium(classifier: RiskClassifier) -> None:
    result = classifier.classify(base_spec(can_generate_synthetic_content=True, user_scope="org"))
    assert result.tier is RiskTier.MEDIUM
    assert "VN-134.11.2.synthetic_any" in result.fired_rule_ids
    assert "Đ11.2" in result.applicable_articles


def test_synthetic_content_public_mass_medium_with_deepfake(
    classifier: RiskClassifier,
) -> None:
    result = classifier.classify(
        base_spec(can_generate_synthetic_content=True, user_scope="public-mass")
    )
    assert result.tier is RiskTier.MEDIUM
    # Public-mass + synthetic fires the deepfake-labeling rule
    assert "VN-134.9.1b.synthetic_public" in result.fired_rule_ids
    assert "Đ11.4" in result.applicable_articles


# ---------------------------------------------------------------------------
# Đ9.1.b — public-mass autonomous
# ---------------------------------------------------------------------------


def test_public_mass_autonomous_chatbot_medium(classifier: RiskClassifier) -> None:
    result = classifier.classify(
        base_spec(
            sector="other",
            automation_level="autonomous",
            user_scope="public-mass",
        )
    )
    assert result.tier is RiskTier.MEDIUM
    assert "VN-134.9.1b.public_mass_autonomous" in result.fired_rule_ids


# ---------------------------------------------------------------------------
# Tier ordering — multiple rules → highest wins
# ---------------------------------------------------------------------------


def test_high_beats_medium_when_both_fire(classifier: RiskClassifier) -> None:
    """Healthcare-autonomous (HIGH) + synthetic content (MEDIUM)
    both fire — result is HIGH."""
    result = classifier.classify(
        base_spec(
            sector="health",
            automation_level="autonomous",
            can_generate_synthetic_content=True,
        )
    )
    assert result.tier is RiskTier.HIGH
    # Both rules' citations land in articles
    assert "Đ6.2.a" in result.applicable_articles
    assert "Đ11.2" in result.applicable_articles


def test_two_high_rules_both_in_reasoning(classifier: RiskClassifier) -> None:
    """Vulnerable + healthcare-autonomous: both HIGH, both must
    appear in reasoning."""
    result = classifier.classify(
        base_spec(
            sector="health",
            automation_level="autonomous",
            affects_vulnerable_groups=True,
        )
    )
    assert result.tier is RiskTier.HIGH
    assert len(result.reasoning) >= 2
    assert any("vulnerable" in rid for rid in result.fired_rule_ids)
    assert any("health" in rid for rid in result.fired_rule_ids)


# ---------------------------------------------------------------------------
# Result invariants
# ---------------------------------------------------------------------------


def test_result_articles_are_deduplicated(classifier: RiskClassifier) -> None:
    """Multiple rules can cite the same article; output must dedup."""
    result = classifier.classify(
        base_spec(
            sector="health",
            automation_level="autonomous",
            affects_vulnerable_groups=True,
        )
    )
    arts = list(result.applicable_articles)
    assert len(arts) == len(set(arts))


def test_result_is_frozen() -> None:
    result = ClassificationResult(
        tier=RiskTier.LOW,
        applicable_articles=("Đ9.1.c",),
        reasoning=("ok",),
    )
    with pytest.raises(AttributeError):
        result.tier = RiskTier.HIGH  # type: ignore[misc]


def test_system_spec_is_frozen() -> None:
    spec = base_spec()
    with pytest.raises(AttributeError):
        spec.sector = "health"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Custom rule table
# ---------------------------------------------------------------------------


def test_classifier_accepts_custom_rules() -> None:
    """A bank can ship a stricter local table; the classifier honors it."""
    from nom.compliance.risk.rules import Rule

    custom = Rule(
        rule_id="bank-policy-001",
        tier=RiskTier.HIGH,
        articles=("Đ9.1.a", "internal-policy-001"),
        reason="Bank internal policy: any customer-facing AI is HIGH.",
        predicate=lambda s: s.user_scope == "public-mass",
    )
    cls = RiskClassifier(rules=(custom,))
    result = cls.classify(base_spec(user_scope="public-mass"))
    assert result.tier is RiskTier.HIGH
    assert "bank-policy-001" in result.fired_rule_ids
    assert "internal-policy-001" in result.applicable_articles


def test_empty_rules_always_low() -> None:
    cls = RiskClassifier(rules=())
    # Even healthcare-autonomous returns LOW with no rules.
    result = cls.classify(base_spec(sector="health", automation_level="autonomous"))
    assert result.tier is RiskTier.LOW
