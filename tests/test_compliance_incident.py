"""Tests for ``nom.compliance.incident``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nom.compliance import AuditLog
from nom.compliance.incident import (
    IncidentCategory,
    IncidentRecorder,
    IncidentSeverity,
    incident_report_dict,
)


@pytest.fixture
def recorder(tmp_path: Path) -> IncidentRecorder:
    return IncidentRecorder(path=tmp_path / "incidents.jsonl")


def test_record_creates_jsonl_entry(recorder: IncidentRecorder, tmp_path: Path) -> None:
    incident = recorder.record(
        severity=IncidentSeverity.HIGH,
        categories=[IncidentCategory.LIFE_HEALTH],
        summary="Mô hình tư vấn sai liều thuốc",
        system_name="MedAdvisor",
        affected_persons_estimate=2,
    )
    assert incident.system_name == "MedAdvisor"
    assert incident.severity is IncidentSeverity.HIGH
    contents = (tmp_path / "incidents.jsonl").read_text()
    line = json.loads(contents.splitlines()[0])
    assert line["severity"] == "high"
    assert line["categories"] == ["life-health"]
    assert line["affected_persons_estimate"] == 2


def test_record_rejects_empty_categories(recorder: IncidentRecorder) -> None:
    with pytest.raises(ValueError, match="at least one IncidentCategory"):
        recorder.record(
            severity=IncidentSeverity.LOW,
            categories=[],
            summary="x",
            system_name="x",
        )


def test_all_returns_records_in_order(recorder: IncidentRecorder) -> None:
    for i in range(3):
        recorder.record(
            severity=IncidentSeverity.LOW,
            categories=[IncidentCategory.OTHER],
            summary=f"event {i}",
            system_name="sys",
        )
    incidents = recorder.all()
    assert [i.summary for i in incidents] == ["event 0", "event 1", "event 2"]


def test_record_with_audit_log_chains(tmp_path: Path) -> None:
    audit = AuditLog.sqlite(tmp_path / "a.db", signing_key=b"x" * 32)
    rec = IncidentRecorder(path=tmp_path / "incidents.jsonl", audit_log=audit)
    rec.record(
        severity=IncidentSeverity.CRITICAL,
        categories=[IncidentCategory.NATIONAL_SECURITY_INFRA],
        summary="Hệ thống thông tin trọng yếu bị gián đoạn",
        system_name="GovBot",
    )
    events = list(audit.store.iter_events())
    assert len(events) == 1
    assert events[0].action == "incident.recorded"
    assert events[0].risk_tier == "high"  # CRITICAL maps to high tier
    assert audit.verify().ok is True


def test_incident_report_dict_shape() -> None:
    rec_path = Path("/tmp/x_incidents.jsonl")
    rec = IncidentRecorder(path=rec_path)
    incident = rec.record(
        severity=IncidentSeverity.MEDIUM,
        categories=[IncidentCategory.HUMAN_RIGHTS, IncidentCategory.OTHER],
        summary="Phân biệt đối xử trong xếp loại tín dụng",
        system_name="CreditScorer",
    )
    payload = incident_report_dict(
        incident,
        provider_name="ACME AI Co.",
        provider_contact="legal@acme.vn",
        deployer_name="Bank ABC",
        deployer_contact="risk@bankabc.vn",
        mitigation_taken="Tạm dừng hệ thống và triển khai bản vá.",
    )
    assert payload["law_reference"] == "VN-134/2025"
    assert payload["article"] == "Đ12"
    assert payload["incident"]["severity"] == "medium"
    assert "human-rights" in payload["incident"]["categories"]
    assert payload["provider"]["name"] == "ACME AI Co."
    assert payload["deployer"]["name"] == "Bank ABC"
    assert payload["mitigation_taken"].startswith("Tạm dừng")


def test_incident_report_dict_no_deployer_yields_none() -> None:
    rec = IncidentRecorder(path=Path("/tmp/y_incidents.jsonl"))
    incident = rec.record(
        severity=IncidentSeverity.LOW,
        categories=[IncidentCategory.OTHER],
        summary="x",
        system_name="x",
    )
    payload = incident_report_dict(incident, provider_name="P", provider_contact="c")
    assert payload["deployer"] is None
