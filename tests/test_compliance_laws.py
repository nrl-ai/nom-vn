"""Tests for ``nom.compliance.laws`` — LawSpec + registry + VN-134 data."""

from __future__ import annotations

from dataclasses import replace

import pytest

from nom.compliance import RiskTier
from nom.compliance.laws import (
    LAW_VN_134_2025,
    LawSpec,
    PendingDecree,
    RuleSpec,
    SectorSpec,
    available,
    get,
)

# ---------------------------------------------------------------------------
# LawSpec — registry + introspection
# ---------------------------------------------------------------------------


def test_vn_134_law_spec_metadata() -> None:
    law = LAW_VN_134_2025
    assert law.law_id == "VN-134/2025"
    assert law.version == "1.0.0"
    assert law.effective_date == "2026-03-01"
    assert "Quốc hội" in law.authority


def test_vn_134_has_three_tier_articles() -> None:
    law = LAW_VN_134_2025
    assert law.risk_tier_articles[RiskTier.HIGH] == "Đ9.1.a"
    assert law.risk_tier_articles[RiskTier.MEDIUM] == "Đ9.1.b"
    assert law.risk_tier_articles[RiskTier.LOW] == "Đ9.1.c"


def test_vn_134_essential_sectors_are_marked() -> None:
    law = LAW_VN_134_2025
    essential = {s.id for s in law.sectors if s.is_essential}
    assert essential == {"health", "education", "finance"}


def test_vn_134_deadlines_match_article_35() -> None:
    law = LAW_VN_134_2025
    assert law.deadlines["effective"] == "2026-03-01"
    assert law.deadlines["general"] == "2027-03-01"
    assert law.deadlines["health"] == "2027-09-01"
    assert law.deadlines["education"] == "2027-09-01"
    assert law.deadlines["finance"] == "2027-09-01"


def test_vn_134_pending_decrees_present() -> None:
    law = LAW_VN_134_2025
    decree_articles = {d.article for d in law.pending_decrees}
    assert "Đ8.4" in decree_articles  # portal API
    assert "Đ13.4" in decree_articles  # PM Danh mục
    assert "Đ27.5" in decree_articles  # state-use impact


def test_vn_134_rule_count() -> None:
    """The current rule set covers all 9 named cases."""
    assert len(LAW_VN_134_2025.rules) == 9


def test_vn_134_each_rule_has_articles_and_reason() -> None:
    for rule in LAW_VN_134_2025.rules:
        assert rule.rule_id.startswith("VN-134.")
        assert rule.articles, f"Rule {rule.rule_id} has no articles"
        assert rule.reason_vi, f"Rule {rule.rule_id} has no reason"
        assert rule.tier in {RiskTier.HIGH, RiskTier.MEDIUM, RiskTier.LOW}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_lists_known_laws() -> None:
    laws = available()
    assert "VN-134/2025" in laws


def test_registry_get_returns_law_spec() -> None:
    law = get("VN-134/2025")
    assert isinstance(law, LawSpec)
    assert law.law_id == "VN-134/2025"


def test_registry_get_unknown_raises_with_helpful_message() -> None:
    with pytest.raises(KeyError) as exc:
        get("EU-AI-Act")
    msg = str(exc.value)
    assert "EU-AI-Act" in msg
    assert "VN-134/2025" in msg


# ---------------------------------------------------------------------------
# Versioning — replace gives a derived spec without mutating the constant
# ---------------------------------------------------------------------------


def test_replace_does_not_mutate_canonical() -> None:
    law_v2 = replace(LAW_VN_134_2025, version="2.0.0")
    assert law_v2.version == "2.0.0"
    # Original unchanged
    assert LAW_VN_134_2025.version == "1.0.0"


def test_law_spec_is_frozen() -> None:
    """LawSpec mutates only via dataclasses.replace."""
    with pytest.raises(AttributeError):
        LAW_VN_134_2025.version = "2.0.0"  # type: ignore[misc]


def test_rule_spec_is_frozen() -> None:
    rule = LAW_VN_134_2025.rules[0]
    with pytest.raises(AttributeError):
        rule.tier = RiskTier.LOW  # type: ignore[misc]


def test_sector_spec_is_frozen() -> None:
    health = next(s for s in LAW_VN_134_2025.sectors if s.id == "health")
    with pytest.raises(AttributeError):
        health.is_essential = False  # type: ignore[misc]


def test_pending_decree_is_frozen() -> None:
    decree = LAW_VN_134_2025.pending_decrees[0]
    with pytest.raises(AttributeError):
        decree.status_note = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Future-law slot — check the abstraction is generic
# ---------------------------------------------------------------------------


def test_lawspec_can_construct_a_minimal_synthetic_law() -> None:
    """Sanity-check that LawSpec works as a generic abstraction by
    constructing a tiny fake law with one rule."""
    fake = LawSpec(
        law_id="TEST-001",
        version="0.1.0",
        title_vi="Luật thử nghiệm",
        title_en="Test law",
        issued_date="2026-01-01",
        effective_date="2026-06-01",
        authority="Test",
        risk_tier_articles={
            RiskTier.HIGH: "Art.1",
            RiskTier.MEDIUM: "Art.2",
            RiskTier.LOW: "Art.3",
        },
        sectors=(SectorSpec(id="other", title_vi="Khác", title_en="Other"),),
        rules=(
            RuleSpec(
                rule_id="TEST.always_high",
                tier=RiskTier.HIGH,
                articles=("Art.1",),
                reason_vi="Always high in test law",
                predicate=lambda s: True,
            ),
        ),
        deadlines={"effective": "2026-06-01"},
        pending_decrees=(PendingDecree("Art.99", "Future regulations"),),
    )
    assert fake.law_id == "TEST-001"
    assert len(fake.rules) == 1
    assert fake.sectors[0].id == "other"
