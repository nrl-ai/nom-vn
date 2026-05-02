"""Vietnam AI Law 134/2025/QH15 — version 1 (initial passage).

Source: full Vietnamese text scanned PDF at
``https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/01/luat134.signed.pdf``
(20 pages, 35 articles, 8 chapters). Cross-checked against
luatvietnam English translation and thuvienphapluat VN portal.

Bump :data:`LAW.version` when an implementing decree publishes that
substantively changes a rule's interpretation. A new module
``vn_134_2025_v2.py`` is fine if the change is large enough to
break old classification reproductions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nom.compliance.laws._types import LawSpec, PendingDecree, RuleSpec, SectorSpec
from nom.compliance.types import RiskTier

if TYPE_CHECKING:
    from nom.compliance.risk.classifier import SystemSpec

__all__ = ["LAW"]


# ---------------------------------------------------------------------------
# Sectors — Đ6.2 named sectors + finance + public-services + other
# ---------------------------------------------------------------------------

_SECTORS: tuple[SectorSpec, ...] = (
    SectorSpec(
        id="health",
        title_vi="Y tế",
        title_en="Healthcare",
        articles=("Đ6.2.a",),
        is_essential=True,
    ),
    SectorSpec(
        id="education",
        title_vi="Giáo dục",
        title_en="Education",
        articles=("Đ6.2.b",),
        is_essential=True,
    ),
    SectorSpec(
        id="finance",
        title_vi="Tài chính",
        title_en="Finance",
        articles=("Đ35.1.a",),  # 18-month grace cohort
        is_essential=True,
    ),
    SectorSpec(
        id="public-services",
        title_vi="Dịch vụ công",
        title_en="Public services",
        articles=("Đ27",),
    ),
    SectorSpec(
        id="other",
        title_vi="Lĩnh vực khác",
        title_en="Other",
    ),
)


# ---------------------------------------------------------------------------
# Rules — predicate lambdas live next to their data; typed, no eval.
# ---------------------------------------------------------------------------


def _vulnerable(spec: SystemSpec) -> bool:
    return spec.affects_vulnerable_groups


def _health_non_advisory(spec: SystemSpec) -> bool:
    return spec.sector == "health" and spec.automation_level != "advisory"


def _health_advisory(spec: SystemSpec) -> bool:
    return spec.sector == "health" and spec.automation_level == "advisory"


def _education_non_advisory(spec: SystemSpec) -> bool:
    return spec.sector == "education" and spec.automation_level != "advisory"


def _finance_non_advisory(spec: SystemSpec) -> bool:
    return spec.sector == "finance" and spec.automation_level != "advisory"


def _public_services_autonomous(spec: SystemSpec) -> bool:
    return (
        spec.sector == "public-services"
        and spec.automation_level == "autonomous"
        and spec.user_scope == "public-mass"
    )


def _synthetic_public(spec: SystemSpec) -> bool:
    return spec.can_generate_synthetic_content and spec.user_scope == "public-mass"


def _synthetic_other(spec: SystemSpec) -> bool:
    return spec.can_generate_synthetic_content and spec.user_scope != "public-mass"


def _public_mass_autonomous(spec: SystemSpec) -> bool:
    return (
        spec.user_scope == "public-mass"
        and spec.automation_level == "autonomous"
        and spec.sector not in {"health", "education", "finance", "public-services"}
    )


_RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        rule_id="VN-134.7.2c.vulnerable",
        tier=RiskTier.HIGH,
        articles=("Đ7.2.c", "Đ9.1.a"),
        reason_vi=(
            "Hệ thống có khả năng tác động đến nhóm dễ bị tổn thương "
            "(trẻ em, người cao tuổi, người khuyết tật, dân tộc thiểu số). "
            "Đ7.2.c cấm khai thác điểm yếu nhóm này; phân loại HIGH để "
            "kích hoạt nghĩa vụ Đ14."
        ),
        predicate=_vulnerable,
    ),
    RuleSpec(
        rule_id="VN-134.6.2a.health.non_advisory",
        tier=RiskTier.HIGH,
        articles=("Đ6.2.a", "Đ9.1.a"),
        reason_vi=(
            "Lĩnh vực y tế (Đ6.2.a) với mức tự chủ semi-autonomous hoặc "
            "autonomous: tác động trực tiếp đến tính mạng, sức khỏe → Đ9.1.a."
        ),
        predicate=_health_non_advisory,
    ),
    RuleSpec(
        rule_id="VN-134.6.2a.health.advisory",
        tier=RiskTier.MEDIUM,
        articles=("Đ6.2.a", "Đ9.1.b", "Đ11"),
        reason_vi=(
            "Lĩnh vực y tế (Đ6.2.a) ở mức advisory: vẫn cần minh bạch + "
            "cảnh báo Đ11 để người dùng không nhầm là chẩn đoán y khoa."
        ),
        predicate=_health_advisory,
    ),
    RuleSpec(
        rule_id="VN-134.6.2b.education.non_advisory",
        tier=RiskTier.HIGH,
        articles=("Đ6.2.b", "Đ9.1.a"),
        reason_vi=(
            "Lĩnh vực giáo dục (Đ6.2.b) với mức tự chủ semi/autonomous: "
            "đánh giá, phân loại học viên có thể tác động đến phát triển "
            "→ Đ9.1.a."
        ),
        predicate=_education_non_advisory,
    ),
    RuleSpec(
        rule_id="VN-134.35.1a.finance.non_advisory",
        tier=RiskTier.HIGH,
        articles=("Đ9.1.a", "Đ35.1.a"),
        reason_vi=(
            "Lĩnh vực tài chính ở mức tự chủ semi/autonomous: tác động "
            "đến quyền và lợi ích hợp pháp (cho vay, bảo hiểm, chấm điểm) "
            "→ Đ9.1.a. Đ35.1.a cho phép 18 tháng chuyển tiếp."
        ),
        predicate=_finance_non_advisory,
    ),
    RuleSpec(
        rule_id="VN-134.27.public_services.autonomous",
        tier=RiskTier.HIGH,
        articles=("Đ9.1.a", "Đ27.3"),
        reason_vi=(
            "Dịch vụ công ở mức autonomous với phạm vi public-mass: rơi "
            "vào diện 'sử dụng trong quản lý nhà nước' (Đ27); cần báo cáo "
            "đánh giá tác động (Đ27.3)."
        ),
        predicate=_public_services_autonomous,
    ),
    RuleSpec(
        rule_id="VN-134.9.1b.synthetic_public",
        tier=RiskTier.MEDIUM,
        articles=("Đ9.1.b", "Đ11.2", "Đ11.4"),
        reason_vi=(
            "Hệ thống có thể tạo nội dung tổng hợp + phạm vi public-mass: "
            "rủi ro nhầm lẫn về tính xác thực (Đ9.1.b). Đ11.2/11.4 yêu cầu "
            "đánh dấu nội dung và gắn nhãn deepfake."
        ),
        predicate=_synthetic_public,
    ),
    RuleSpec(
        rule_id="VN-134.11.2.synthetic_any",
        tier=RiskTier.MEDIUM,
        articles=("Đ9.1.b", "Đ11.2"),
        reason_vi=(
            "Hệ thống có thể tạo nội dung tổng hợp: kích hoạt Đ11.2 đánh "
            "dấu định dạng máy đọc để tránh nhầm lẫn (Đ9.1.b)."
        ),
        predicate=_synthetic_other,
    ),
    RuleSpec(
        rule_id="VN-134.9.1b.public_mass_autonomous",
        tier=RiskTier.MEDIUM,
        articles=("Đ9.1.b", "Đ11.1"),
        reason_vi=(
            "Phạm vi public-mass + tự chủ autonomous mà không thuộc lĩnh "
            "vực thiết yếu: rủi ro thao túng / nhầm lẫn (Đ9.1.b); cần "
            "minh bạch Đ11.1."
        ),
        predicate=_public_mass_autonomous,
    ),
)


# ---------------------------------------------------------------------------
# Pending decrees — items the law defers to Government / PM
# ---------------------------------------------------------------------------

_PENDING: tuple[PendingDecree, ...] = (
    PendingDecree(
        "Đ8.4",
        "Cơ chế Cổng thông tin một cửa + CSDL quốc gia AI",
        "Defer registry helper to v0.4 once portal API publishes",
    ),
    PendingDecree("Đ9.3", "Chi tiết phân loại rủi ro", "Rule table tunable; structure unchanged"),
    PendingDecree(
        "Đ10.7",
        "Nội dung + thủ tục thông báo",
        "Adapter from ClassificationDossier to official format",
    ),
    PendingDecree(
        "Đ11.6", "Format đánh dấu nội dung AI machine-readable", "Translator C2PA → official format"
    ),
    PendingDecree(
        "Đ12.5", "Chi tiết báo cáo sự cố", "Adapter from incident_report_dict to portal API"
    ),
    PendingDecree(
        "Đ13.4",
        "Danh mục hệ thống bắt buộc chứng nhận (PM)",
        "ConformityPackage MVP → full when published",
    ),
    PendingDecree("Đ13.6", "Quy trình đánh giá sự phù hợp", ""),
    PendingDecree("Đ14.7", "Chi tiết quản lý high-risk", ""),
    PendingDecree(
        "Đ27.5", "Quy trình đánh giá tác động AI nhà nước", "ImpactAssessment MVP → full"
    ),
    PendingDecree("Đ29.5", "Khung xử phạt hành chính", ""),
    PendingDecree("Đ31", "An ninh thông tin trong cung cấp dữ liệu", ""),
)


# ---------------------------------------------------------------------------
# The exported LawSpec
# ---------------------------------------------------------------------------

LAW: LawSpec = LawSpec(
    law_id="VN-134/2025",
    version="1.0.0",
    title_vi="Luật Trí tuệ nhân tạo (134/2025/QH15)",
    title_en="Vietnam AI Law (134/2025/QH15)",
    issued_date="2025-12-10",
    effective_date="2026-03-01",
    authority="Quốc hội nước CHXHCN Việt Nam khóa XV",
    risk_tier_articles={
        RiskTier.HIGH: "Đ9.1.a",
        RiskTier.MEDIUM: "Đ9.1.b",
        RiskTier.LOW: "Đ9.1.c",
    },
    sectors=_SECTORS,
    rules=_RULES,
    deadlines={
        "effective": "2026-03-01",
        "general": "2027-03-01",
        "health": "2027-09-01",
        "education": "2027-09-01",
        "finance": "2027-09-01",
    },
    pending_decrees=_PENDING,
    transparency_articles=("Đ11.1",),
    data_governance_article="Đ7.3",
    high_risk_obligations_articles=("Đ9.1.a", "Đ10.3", "Đ13", "Đ14.1"),
    medium_risk_obligations_articles=("Đ9.1.b", "Đ10.3", "Đ15.1"),
    low_risk_obligations_articles=("Đ9.1.c", "Đ15.2"),
)
