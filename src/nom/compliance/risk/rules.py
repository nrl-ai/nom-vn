"""Default rule table — each rule cites the article(s) that justify it.

Rules are evaluated in declaration order, but the classifier picks the
highest tier any rule asserts (so the table can be in arbitrary
order). Each rule's ``rule_id`` is what shows up in
:class:`ClassificationResult.fired_rule_ids` so a legal reviewer can
trace each decision back to its exact rule.

Editing this table changes the legal interpretation of nom.compliance.
Treat it like a config file with the same review weight as a contract
clause: changes go through a PR with a citation in the description.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nom.compliance.types import RiskTier

if TYPE_CHECKING:
    from nom.compliance.risk.classifier import SystemSpec

__all__ = ["RULE_TABLE", "Rule"]


@dataclass(frozen=True, slots=True)
class Rule:
    """One rule in the table.

    ``predicate`` is a small lambda over a SystemSpec; if it returns
    True the rule's tier and articles are merged into the result.
    """

    rule_id: str
    tier: RiskTier
    articles: tuple[str, ...]
    reason: str
    predicate: Callable[[SystemSpec], bool]

    def matches(self, spec: SystemSpec) -> bool:
        return self.predicate(spec)


# Đ7.2.c — exploiting vulnerabilities of vulnerable groups is a
# prohibited act, not just high-risk. We don't *block* the system at
# classification time (that's a runtime guardrail, not a tier label),
# but any system that *can affect* vulnerable groups gets HIGH so
# the operator knows they're stepping into Đ7 / Đ14 territory.
_VULNERABLE_GROUPS = Rule(
    rule_id="VN-134.7.2c.vulnerable",
    tier=RiskTier.HIGH,
    articles=("Đ7.2.c", "Đ9.1.a"),
    reason=(
        "Hệ thống có khả năng tác động đến nhóm dễ bị tổn thương "
        "(trẻ em, người cao tuổi, người khuyết tật, dân tộc thiểu số). "
        "Đ7.2.c cấm khai thác điểm yếu nhóm này; phân loại HIGH để "
        "kích hoạt nghĩa vụ Đ14."
    ),
    predicate=lambda s: s.affects_vulnerable_groups,
)


# Đ6.2.a — healthcare is an explicit essential sector. Any
# non-advisory deployment in healthcare carries direct life/health
# impact (Đ9.1.a).
_HEALTHCARE_NON_ADVISORY = Rule(
    rule_id="VN-134.6.2a.health.non_advisory",
    tier=RiskTier.HIGH,
    articles=("Đ6.2.a", "Đ9.1.a"),
    reason=(
        "Lĩnh vực y tế (Đ6.2.a) với mức tự chủ semi-autonomous hoặc "
        "autonomous: tác động trực tiếp đến tính mạng, sức khỏe → Đ9.1.a."
    ),
    predicate=lambda s: s.sector == "health" and s.automation_level != "advisory",
)


# Healthcare-advisory still warrants MEDIUM because Đ6.2.a applies
# regardless and confused users may follow advisory output without
# clinical judgement.
_HEALTHCARE_ADVISORY = Rule(
    rule_id="VN-134.6.2a.health.advisory",
    tier=RiskTier.MEDIUM,
    articles=("Đ6.2.a", "Đ9.1.b", "Đ11"),
    reason=(
        "Lĩnh vực y tế (Đ6.2.a) ở mức advisory: vẫn cần minh bạch + "
        "cảnh báo Đ11 để người dùng không nhầm là chẩn đoán y khoa."
    ),
    predicate=lambda s: s.sector == "health" and s.automation_level == "advisory",
)


# Đ6.2.b — education is the second named essential sector.
# Same logic as healthcare: non-advisory → HIGH, advisory → MEDIUM.
_EDUCATION_NON_ADVISORY = Rule(
    rule_id="VN-134.6.2b.education.non_advisory",
    tier=RiskTier.HIGH,
    articles=("Đ6.2.b", "Đ9.1.a"),
    reason=(
        "Lĩnh vực giáo dục (Đ6.2.b) với mức tự chủ semi/autonomous: "
        "đánh giá, phân loại học viên có thể tác động đến phát triển "
        "→ Đ9.1.a."
    ),
    predicate=lambda s: s.sector == "education" and s.automation_level != "advisory",
)


# Finance is the third sector with an 18-month grace per Đ35.1.a;
# treat decisions affecting "quyền và lợi ích hợp pháp" (loans,
# credit scores, insurance pricing) as HIGH when non-advisory.
_FINANCE_NON_ADVISORY = Rule(
    rule_id="VN-134.35.1a.finance.non_advisory",
    tier=RiskTier.HIGH,
    articles=("Đ9.1.a", "Đ35.1.a"),
    reason=(
        "Lĩnh vực tài chính ở mức tự chủ semi/autonomous: tác động "
        "đến quyền và lợi ích hợp pháp (cho vay, bảo hiểm, chấm điểm) "
        "→ Đ9.1.a. Đ35.1.a cho phép 18 tháng chuyển tiếp."
    ),
    predicate=lambda s: s.sector == "finance" and s.automation_level != "advisory",
)


# Public services + autonomous + public-mass scope = state-touching
# AI, which Đ27 specifically addresses (impact assessment required).
_PUBLIC_SERVICES_AUTONOMOUS = Rule(
    rule_id="VN-134.27.public_services.autonomous",
    tier=RiskTier.HIGH,
    articles=("Đ9.1.a", "Đ27.3"),
    reason=(
        "Dịch vụ công ở mức autonomous với phạm vi public-mass: rơi "
        "vào diện 'sử dụng trong quản lý nhà nước' (Đ27); cần báo cáo "
        "đánh giá tác động (Đ27.3)."
    ),
    predicate=lambda s: (
        s.sector == "public-services"
        and s.automation_level == "autonomous"
        and s.user_scope == "public-mass"
    ),
)


# Đ9.1.b — synthetic content in a public-mass context is the textbook
# medium-risk case (deepfake / AI-generated content the public might
# mistake for real). Đ11.2 + Đ11.4 obligations apply.
_SYNTHETIC_CONTENT_PUBLIC = Rule(
    rule_id="VN-134.9.1b.synthetic_public",
    tier=RiskTier.MEDIUM,
    articles=("Đ9.1.b", "Đ11.2", "Đ11.4"),
    reason=(
        "Hệ thống có thể tạo nội dung tổng hợp + phạm vi public-mass: "
        "rủi ro nhầm lẫn về tính xác thực (Đ9.1.b). Đ11.2/11.4 yêu cầu "
        "đánh dấu nội dung và gắn nhãn deepfake."
    ),
    predicate=lambda s: s.can_generate_synthetic_content and s.user_scope == "public-mass",
)


# Synthetic content for any audience still triggers Đ11.2 marking
# (machine-readable provenance), so MEDIUM. The public-mass rule
# above adds Đ11.4 deepfake labeling.
_SYNTHETIC_CONTENT_ANY = Rule(
    rule_id="VN-134.11.2.synthetic_any",
    tier=RiskTier.MEDIUM,
    articles=("Đ9.1.b", "Đ11.2"),
    reason=(
        "Hệ thống có thể tạo nội dung tổng hợp: kích hoạt Đ11.2 đánh "
        "dấu định dạng máy đọc để tránh nhầm lẫn (Đ9.1.b)."
    ),
    predicate=lambda s: s.can_generate_synthetic_content and s.user_scope != "public-mass",
)


# Public-mass interaction with autonomous decision-making → MEDIUM
# at minimum (consumer-facing chatbot acting on user intent).
_PUBLIC_MASS_AUTONOMOUS = Rule(
    rule_id="VN-134.9.1b.public_mass_autonomous",
    tier=RiskTier.MEDIUM,
    articles=("Đ9.1.b", "Đ11.1"),
    reason=(
        "Phạm vi public-mass + tự chủ autonomous mà không thuộc lĩnh "
        "vực thiết yếu: rủi ro thao túng / nhầm lẫn (Đ9.1.b); cần "
        "minh bạch Đ11.1."
    ),
    predicate=lambda s: (
        s.user_scope == "public-mass"
        and s.automation_level == "autonomous"
        and s.sector not in ("health", "education", "finance", "public-services")
    ),
)


RULE_TABLE: tuple[Rule, ...] = (
    _VULNERABLE_GROUPS,
    _HEALTHCARE_NON_ADVISORY,
    _HEALTHCARE_ADVISORY,
    _EDUCATION_NON_ADVISORY,
    _FINANCE_NON_ADVISORY,
    _PUBLIC_SERVICES_AUTONOMOUS,
    _SYNTHETIC_CONTENT_PUBLIC,
    _SYNTHETIC_CONTENT_ANY,
    _PUBLIC_MASS_AUTONOMOUS,
)
