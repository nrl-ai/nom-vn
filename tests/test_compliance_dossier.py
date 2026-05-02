"""Tests for ``nom.compliance.dossier``."""

from __future__ import annotations

from pathlib import Path

import pytest

from nom.compliance import AuditLog, RiskClassifier, RiskTier, SystemSpec
from nom.compliance.dossier import (
    ClassificationDossier,
    ConformityPackage,
    ImpactAssessment,
    TechnicalDossier,
)


@pytest.fixture
def spec() -> SystemSpec:
    return SystemSpec(
        purpose="Trợ lý hỏi-đáp hợp đồng",
        sector="finance",
        automation_level="advisory",
        user_scope="org",
        handles_personal_data=True,
        affects_vulnerable_groups=False,
        can_generate_synthetic_content=False,
    )


@pytest.fixture
def classification(spec: SystemSpec) -> object:
    return RiskClassifier().classify(spec)


@pytest.fixture
def audit_log(tmp_path: Path) -> AuditLog:
    log = AuditLog.sqlite(tmp_path / "audit.db", signing_key=b"a" * 32)
    log.emit(actor="rag:ask", action="ask", payload={"q": "x"}, risk_tier=RiskTier.MEDIUM)
    log.emit(actor="llm:ollama", action="complete", payload={"p": "x"})
    log.emit(actor="rag:ask", action="ask.ok", payload={"n": 1})
    return log


# ---------------------------------------------------------------------------
# ClassificationDossier
# ---------------------------------------------------------------------------


def test_classification_dossier_renders_vi(spec: SystemSpec, classification: object) -> None:
    dossier = ClassificationDossier.from_classification(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        provider_name="ACME AI",
        provider_contact="legal@acme.vn",
    )
    out = dossier.render(language="vi")
    assert "Hồ sơ phân loại" in out
    assert "Luật 134/2025" in out
    assert "ACME AI" in out
    assert "Trợ lý hỏi-đáp hợp đồng" in out
    # Article cites surface
    assert "Đ" in out


def test_classification_dossier_renders_en(spec: SystemSpec, classification: object) -> None:
    dossier = ClassificationDossier.from_classification(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        provider_name="ACME AI",
        provider_contact="legal@acme.vn",
    )
    out = dossier.render(language="en")
    assert "Classification Dossier" in out
    assert "ACME AI" in out


def test_classification_dossier_with_deployer(spec: SystemSpec, classification: object) -> None:
    dossier = ClassificationDossier.from_classification(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        provider_name="P",
        provider_contact="p@x",
        deployer_name="Bank ABC",
        deployer_contact="risk@abc.vn",
    )
    out = dossier.render()
    assert "Bank ABC" in out


def test_classification_dossier_writes_file(
    spec: SystemSpec, classification: object, tmp_path: Path
) -> None:
    dossier = ClassificationDossier.from_classification(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        provider_name="P",
        provider_contact="c",
    )
    out_path = dossier.write(tmp_path / "out" / "classification.md")
    assert out_path.exists()
    assert "Hồ sơ phân loại" in out_path.read_text()


# ---------------------------------------------------------------------------
# TechnicalDossier
# ---------------------------------------------------------------------------


def test_technical_dossier_renders_with_audit_summary(
    spec: SystemSpec,
    classification: object,
    audit_log: AuditLog,
) -> None:
    dossier = TechnicalDossier.from_pipeline(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        audit_log=audit_log,
        provider_name="ACME AI",
        provider_contact="legal@acme.vn",
        functional_description="Hệ thống RAG over hợp đồng",
        main_input_data_types=("Câu hỏi tiếng Việt", "Tài liệu PDF"),
        risk_mitigation_measures=("Audit log Đ14.1.c", "Reranker filter"),
        data_governance_notes="Train trên corpus public Apache-2.0",
        human_oversight_design="Mỗi phản hồi có nút phản hồi cho người dùng",
    )
    out = dossier.render(language="vi")
    assert "Hồ sơ kỹ thuật" in out
    assert "Hệ thống RAG over hợp đồng" in out
    assert "Câu hỏi tiếng Việt" in out
    assert "Audit log Đ14.1.c" in out
    # Operational-log summary fields
    assert "rag:ask" in out
    assert "complete" in out
    assert "có" in out  # chain verified text


def test_technical_dossier_chain_verified_flag_negative(
    spec: SystemSpec, classification: object, tmp_path: Path
) -> None:
    """When chain doesn't verify, the dossier surfaces it."""
    log = AuditLog.sqlite(tmp_path / "audit.db", signing_key=b"a" * 32)
    log.emit(actor="x", action="y", payload={})

    # Tamper directly in SQLite to break the chain.
    import sqlite3

    log.close()
    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    conn.execute("UPDATE audit_events SET payload_hash = 'bad' WHERE row_id = 1")
    conn.commit()
    conn.close()
    log = AuditLog.sqlite(tmp_path / "audit.db", signing_key=b"a" * 32)

    dossier = TechnicalDossier.from_pipeline(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        audit_log=log,
        provider_name="P",
        provider_contact="c",
        functional_description="x",
        main_input_data_types=("x",),
        risk_mitigation_measures=("x",),
        data_governance_notes="x",
        human_oversight_design="x",
    )
    out = dossier.render(language="vi")
    assert "KHÔNG" in out  # chain_verified=False renders as "KHÔNG"


def test_technical_dossier_writes_zip_able_md(
    spec: SystemSpec, classification: object, audit_log: AuditLog, tmp_path: Path
) -> None:
    dossier = TechnicalDossier.from_pipeline(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        audit_log=audit_log,
        provider_name="P",
        provider_contact="c",
        functional_description="x",
        main_input_data_types=("x",),
        risk_mitigation_measures=("x",),
        data_governance_notes="x",
        human_oversight_design="x",
    )
    out = dossier.write(tmp_path / "tech.md")
    assert out.exists()
    assert out.read_text().startswith("# Hồ sơ kỹ thuật")


def test_technical_dossier_excludes_source_code_disclaimer(
    spec: SystemSpec, classification: object, audit_log: AuditLog
) -> None:
    """Đ14.1.e exclusion section must surface."""
    dossier = TechnicalDossier.from_pipeline(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        audit_log=audit_log,
        provider_name="P",
        provider_contact="c",
        functional_description="x",
        main_input_data_types=("x",),
        risk_mitigation_measures=("x",),
        data_governance_notes="x",
        human_oversight_design="x",
    )
    out = dossier.render()
    assert "mã nguồn" in out
    assert "thuật toán" in out
    assert "bí mật" in out


# ---------------------------------------------------------------------------
# ConformityPackage (MVP skeleton)
# ---------------------------------------------------------------------------


def test_conformity_package_marks_itself_mvp(spec: SystemSpec, classification: object) -> None:
    pkg = ConformityPackage(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        provider_name="P",
        provider_contact="c",
        declared_mitigation_summary="Áp dụng audit log + reranker filter",
        declared_monitoring_summary="Theo dõi 7 ngày qua audit log",
    )
    out = pkg.render()
    assert "khung MVP" in out
    assert "Đ13.4" in out
    assert "Đ25.1" in out


# ---------------------------------------------------------------------------
# ImpactAssessment (MVP skeleton)
# ---------------------------------------------------------------------------


def test_impact_assessment_skeleton_renders(spec: SystemSpec, classification: object) -> None:
    impact = ImpactAssessment(
        spec=spec,
        classification=classification,  # type: ignore[arg-type]
        agency_name="UBND TP X",
        agency_contact="tin@x.gov.vn",
        identified_risks=("Quyết định sai có thể ảnh hưởng quyền công dân",),
        control_measures=("Có cán bộ rà soát trước khi ban hành",),
        oversight_design="Cán bộ phải xác nhận từng quyết định",
    )
    out = impact.render()
    assert "Đ27" in out
    assert "UBND TP X" in out
    assert "Quyết định sai" in out
    assert "khung MVP" in out.lower() or "MVP" in out
