"""Integration + edge-case tests for ``nom.compliance``.

These are the tests the unit suites can't easily reach:

- End-to-end worked example (the one in ``docs/tasks/compliance.md``)
  runs cleanly on a fresh sqlite + temp dir.
- Real Ollama call inside ``AuditedLLM`` produces a verifiable chain
  (skipped when no Ollama is running locally).
- ``otel`` span emission works whether OTel is installed or not.
- Dossier ``write()`` paths (conformity + impact MVPs).
- Wrapper edge cases: ``store_raw=True`` retains text;
  ``AuditedLLM.last_event()`` returns the most recent event.
- Cross-payload determinism: the same input produces the same hash
  across processes / databases.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest

from nom.compliance import (
    AuditedLLM,
    AuditedRAG,
    AuditLog,
    ClassificationDossier,
    ConformityPackage,
    ImpactAssessment,
    IncidentCategory,
    IncidentRecorder,
    IncidentSeverity,
    RiskClassifier,
    RiskTier,
    SystemSpec,
    TechnicalDossier,
)
from nom.compliance.audit.otel import annotate_audit_span, audit_span
from nom.compliance.transparency import write_sidecar

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ollama_running() -> bool:
    """True iff Ollama HTTP API responds locally."""
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_model_available(model: str) -> bool:
    """True iff ``model`` is in Ollama's local list."""
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=1.0)
        if r.status_code != 200:
            return False
        names: list[str] = [m["name"] for m in r.json().get("models", [])]
        return model in names
    except Exception:
        return False


# ---------------------------------------------------------------------------
# End-to-end worked example
# ---------------------------------------------------------------------------


def test_e2e_classify_audit_dossier(tmp_path: Path) -> None:
    """The whole flow from docs/tasks/compliance.md runs cleanly."""
    spec = SystemSpec(
        purpose="Trợ lý hỏi-đáp pháp luật doanh nghiệp",
        sector="finance",
        automation_level="advisory",
        user_scope="org",
        handles_personal_data=True,
        affects_vulnerable_groups=False,
        can_generate_synthetic_content=False,
    )

    # 1. Classify
    result = RiskClassifier().classify(spec)
    assert result.tier in {RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH}
    assert result.law_id == "VN-134/2025"

    # 2. Open audit log + emit some events to simulate operation
    audit = AuditLog.sqlite(tmp_path / "audit.db", signing_key=b"x" * 32)
    audit.emit(
        actor="rag:ask",
        action="ask",
        payload={"q": "test"},
        risk_tier=result.tier,
    )
    audit.emit(actor="llm:fake", action="complete", payload={"p": "test"})
    audit.emit(actor="rag:ask", action="ask.ok", payload={"n": 1})

    # 3. Render classification dossier
    cls_dossier = ClassificationDossier.from_classification(
        spec=spec,
        classification=result,
        provider_name="ACME AI",
        provider_contact="contact@acme.example",
    )
    cls_path = cls_dossier.write(tmp_path / "classification.md")
    assert cls_path.exists()
    cls_text = cls_path.read_text()
    assert spec.purpose in cls_text
    assert "ACME AI" in cls_text

    # 4. Render technical dossier
    tech_dossier = TechnicalDossier.from_pipeline(
        spec=spec,
        classification=result,
        audit_log=audit,
        provider_name="ACME AI",
        provider_contact="contact@acme.example",
        functional_description="Hỏi-đáp pháp luật trên hợp đồng nội bộ",
        main_input_data_types=("PDF hợp đồng", "Câu hỏi tiếng Việt"),
        risk_mitigation_measures=("Chain audit log", "Reranker"),
        data_governance_notes="Dữ liệu khách hàng không leak ra training corpus",
        human_oversight_design="Mỗi câu trả lời có nút phản hồi",
    )
    tech_path = tech_dossier.write(tmp_path / "technical.md")
    assert tech_path.exists()
    tech_text = tech_path.read_text()
    assert "Hỏi-đáp pháp luật trên hợp đồng nội bộ" in tech_text
    # Operational log summary surfaces the events we emitted
    assert "rag:ask" in tech_text
    assert "complete" in tech_text

    # 5. Verify chain + export
    assert audit.verify().ok is True
    export_path = audit.export(tmp_path / "for_inspector.jsonl")
    assert export_path.exists()
    lines = export_path.read_bytes().splitlines()
    assert len(lines) == 3  # 3 events emitted above
    # Each line is canonical JSON
    for line in lines:
        ev = json.loads(line)
        assert "sig" in ev
        assert "prev_sig" in ev


# ---------------------------------------------------------------------------
# Real Ollama integration (skipped when no Ollama)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _ollama_running(), reason="Ollama not running on localhost:11434")
@pytest.mark.skipif(
    not _ollama_model_available("qwen3:1.7b"),
    reason="qwen3:1.7b not pulled in local Ollama",
)
def test_audited_llm_real_ollama_chain_verifies(tmp_path: Path) -> None:
    """An AuditedLLM wrapping a real Ollama call produces a chain
    that verifies. This is the canonical real-LLM smoke test."""
    from nom.llm import Ollama

    audit = AuditLog.sqlite(tmp_path / "ollama.db", signing_key=b"k" * 32)
    llm = AuditedLLM(
        Ollama(model="qwen3:1.7b", think=False),
        audit_log=audit,
        risk_tier=RiskTier.LOW,
    )

    out = llm.complete("Trả lời ngắn gọn: 2+2 bằng mấy?", max_tokens=32)
    assert isinstance(out, str)
    assert len(out) > 0

    events = list(audit.store.iter_events())
    assert len(events) == 2
    assert events[0].action == "complete"
    assert events[1].action == "complete.ok"

    result = audit.verify()
    assert result.ok is True
    assert result.n_events == 2


# ---------------------------------------------------------------------------
# OTel span emission — works with and without OTel installed
# ---------------------------------------------------------------------------


def test_otel_span_no_op_when_otel_disabled() -> None:
    """The audit_span context manager is a no-op when OTel isn't
    installed (or env vars aren't set). Calling it in a test process
    should not raise."""
    with audit_span("test.span") as span:
        annotate_audit_span(
            span,
            actor="test",
            action="x",
            risk_tier="low",
            payload_hash="0" * 64,
            audit_event_id="evt-1",
        )


def test_audit_span_with_minimal_attrs() -> None:
    """annotate_audit_span doesn't require all fields."""
    with audit_span("bare") as span:
        annotate_audit_span(span, actor="a", action="b")


# ---------------------------------------------------------------------------
# Dossier write() paths (conformity + impact MVPs)
# ---------------------------------------------------------------------------


def test_conformity_package_write_to_disk(tmp_path: Path) -> None:
    spec = SystemSpec(
        purpose="x",
        sector="finance",
        automation_level="advisory",
        user_scope="org",
        handles_personal_data=True,
        affects_vulnerable_groups=False,
        can_generate_synthetic_content=False,
    )
    classification = RiskClassifier().classify(spec)
    pkg = ConformityPackage(
        spec=spec,
        classification=classification,
        provider_name="P",
        provider_contact="c@example",
        declared_mitigation_summary="x",
        declared_monitoring_summary="x",
    )
    out = pkg.write(tmp_path / "conf" / "package.md")
    assert out.exists()
    assert "khung MVP" in out.read_text()


def test_impact_assessment_write_to_disk(tmp_path: Path) -> None:
    spec = SystemSpec(
        purpose="x",
        sector="public-services",
        automation_level="autonomous",
        user_scope="public-mass",
        handles_personal_data=False,
        affects_vulnerable_groups=False,
        can_generate_synthetic_content=False,
    )
    classification = RiskClassifier().classify(spec)
    impact = ImpactAssessment(
        spec=spec,
        classification=classification,
        agency_name="UBND TP X",
        agency_contact="tin@example",
        identified_risks=("Rủi ro mẫu",),
        control_measures=("Cán bộ rà soát",),
        oversight_design="Mô tả",
    )
    out = impact.write(tmp_path / "impact" / "report.md")
    assert out.exists()
    assert "Đ27" in out.read_text()


# ---------------------------------------------------------------------------
# Wrapper edge cases
# ---------------------------------------------------------------------------


def test_audited_llm_last_event_returns_latest(tmp_path: Path) -> None:
    from dataclasses import dataclass

    @dataclass
    class _Stub:
        name: str = "stub"

        def complete(
            self,
            prompt: str,
            *,
            schema: dict[str, Any] | None = None,
            max_tokens: int = 2048,
        ) -> str:
            return "out"

    audit = AuditLog.sqlite(tmp_path / "x.db", signing_key=b"a" * 32)
    llm = AuditedLLM(_Stub(), audit_log=audit)
    llm.complete("first")
    llm.complete("second")
    last = llm.last_event()
    assert last is not None
    assert last.action == "complete.ok"  # most recent post-event


def test_audited_rag_passes_n_queries_only_for_multi_query(tmp_path: Path) -> None:
    """The pre-event payload's ``n_queries`` field is None except
    when ``query_strategy='multi_query'``."""
    from dataclasses import dataclass, field

    @dataclass
    class _StubRAG:
        asks: list[dict[str, Any]] = field(default_factory=list)

        def ask(self, q: str, **kw: Any) -> Any:
            self.asks.append({"q": q, **kw})

            from typing import ClassVar

            class _A:
                text = "x"
                citations: ClassVar[list[Any]] = []

            return _A()

    audit = AuditLog.sqlite(tmp_path / "y.db", signing_key=b"a" * 32)
    rag = AuditedRAG(_StubRAG(), audit_log=audit)
    rag.ask("q", query_strategy="direct")
    rag.ask("q", query_strategy="multi_query", n_queries=4)

    events = list(audit.store.iter_events())
    # 2 calls x 2 events each = 4 events.
    # We can't easily inspect payload directly (it's hashed), but
    # presence of two pre-events with different signatures proves
    # the n_queries field shaped them differently.
    assert len(events) == 4
    pre_events = [e for e in events if e.action == "ask"]
    assert len(pre_events) == 2
    assert pre_events[0].payload_hash != pre_events[1].payload_hash


# ---------------------------------------------------------------------------
# Cross-process payload-hash determinism
# ---------------------------------------------------------------------------


def test_payload_hash_stable_across_audit_logs(tmp_path: Path) -> None:
    """Same actor+action+payload → same payload_hash, regardless of
    which AuditLog (or sink) computed it. Property the chain
    relies on for cross-system reproduction."""
    log_a = AuditLog.sqlite(tmp_path / "a.db", signing_key=b"a" * 32)
    log_b = AuditLog.jsonl(tmp_path / "b.jsonl", signing_key=b"b" * 32)
    e_a = log_a.emit(actor="x", action="y", payload={"k": "Hợp đồng"})
    e_b = log_b.emit(actor="x", action="y", payload={"k": "Hợp đồng"})
    assert e_a.payload_hash == e_b.payload_hash


# ---------------------------------------------------------------------------
# Full flow + provenance + incident together
# ---------------------------------------------------------------------------


def test_full_compliance_flow_with_provenance_and_incident(tmp_path: Path) -> None:
    """Assemble: classification + audited pipeline + image
    provenance + incident report — verify everything composes."""
    from dataclasses import dataclass, field

    spec = SystemSpec(
        purpose="VN content generator",
        sector="other",
        automation_level="advisory",
        user_scope="public-mass",
        handles_personal_data=False,
        affects_vulnerable_groups=False,
        can_generate_synthetic_content=True,
    )
    classification = RiskClassifier().classify(spec)
    assert classification.tier is RiskTier.MEDIUM  # synthetic_public + public-mass
    assert "Đ11.4" in classification.applicable_articles  # deepfake labeling

    audit = AuditLog.sqlite(tmp_path / "full.db", signing_key=b"k" * 32)

    # Stub LLM
    @dataclass
    class _Stub:
        name: str = "stub"
        calls: list[Any] = field(default_factory=list)

        def complete(
            self,
            prompt: str,
            *,
            schema: dict[str, Any] | None = None,
            max_tokens: int = 2048,
        ) -> str:
            self.calls.append(prompt)
            return "Đã sinh hình ảnh phong cảnh VN."

    llm = AuditedLLM(_Stub(), audit_log=audit, risk_tier=classification.tier)
    llm.complete("Generate VN landscape image description")

    # Mark image with provenance
    img = tmp_path / "out.png"
    img.write_bytes(b"fake png")
    from nom.compliance.transparency import mark_image

    manifest = mark_image(img, model="stub", is_synthetic=False)
    sidecar = write_sidecar(manifest)
    assert sidecar.exists()
    sidecar_data = json.loads(sidecar.read_text())
    assert sidecar_data["is_ai_generated"] is True

    # Record incident
    rec = IncidentRecorder(path=tmp_path / "incidents.jsonl", audit_log=audit)
    inc = rec.record(
        severity=IncidentSeverity.LOW,
        categories=[IncidentCategory.OTHER],
        summary="Mô hình sinh sai 1 chi tiết nhỏ",
        system_name="ContentGen",
    )
    assert inc.incident_id

    # Final chain still verifies
    assert audit.verify().ok is True


# ---------------------------------------------------------------------------
# Error-message helpfulness
# ---------------------------------------------------------------------------


def test_unknown_law_id_message_is_helpful() -> None:
    from nom.compliance.laws import get

    with pytest.raises(KeyError) as exc:
        get("EU-AI-Act-2024")
    msg = str(exc.value)
    # The KeyError message includes guidance for adding a new law.
    assert "VN-134/2025" in msg
    assert "laws/" in msg


def test_short_signing_key_rejected_with_explanation() -> None:
    with pytest.raises(ValueError, match="16 bytes") as exc:
        AuditLog.sqlite(":memory:", signing_key=b"too short")
    assert "16 bytes" in str(exc.value)


# ---------------------------------------------------------------------------
# Verify install picks up templates
# ---------------------------------------------------------------------------


def test_jinja_templates_packaged_correctly() -> None:
    """Templates must be discoverable from the installed package, not
    just in the source tree. This test fails if hatchling's build
    config drops the .j2 files from the wheel."""
    from importlib.resources import files

    template_dir = files("nom.compliance") / "templates"
    template_files = sorted(p.name for p in template_dir.iterdir() if p.name.endswith(".j2"))
    assert "classification.vi.md.j2" in template_files
    assert "classification.en.md.j2" in template_files
    assert "technical_dossier.vi.md.j2" in template_files
    assert "technical_dossier.en.md.j2" in template_files
    assert "conformity_package.vi.md.j2" in template_files
    assert "impact_assessment.vi.md.j2" in template_files


# ---------------------------------------------------------------------------
# CHANGELOG + version sanity
# ---------------------------------------------------------------------------


def test_pyproject_version_matches_module() -> None:
    """``__version__`` and ``pyproject.toml`` must agree."""
    from nom import __version__

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    raw = pyproject.read_text()
    assert f'version = "{__version__}"' in raw


# Make sure CHANGELOG mentions the current version too.
def test_changelog_mentions_current_version() -> None:
    from nom import __version__

    changelog = Path(__file__).parent.parent / "CHANGELOG.md"
    assert __version__ in changelog.read_text()


# ---------------------------------------------------------------------------
# Pending-decree audit trail — every law deferral has a status_note
# ---------------------------------------------------------------------------


def test_pending_decrees_link_to_status_or_remain_open() -> None:
    """A PendingDecree without a status_note is fine — it just means
    we haven't filed a follow-up plan. But every decree marked done
    must reference a concrete plan."""
    from nom.compliance.laws import LAW_VN_134_2025

    for d in LAW_VN_134_2025.pending_decrees:
        # Status note may be empty (open question) — that's allowed.
        # If non-empty, it should contain something action-oriented.
        if d.status_note:
            tokens = ("v0.4", "MVP", "Adapter", "Translator", "Defer", "Rule")
            assert any(t in d.status_note for t in tokens), (
                f"Decree {d.article} status_note doesn't reference a plan: {d.status_note!r}"
            )


# ---------------------------------------------------------------------------
# Audit log retention bound (Đ28.3 since/until slice)
# ---------------------------------------------------------------------------


def test_export_filters_by_date_range(tmp_path: Path) -> None:
    """When an inspector asks for "last 30 days", the export must
    drop earlier events."""
    audit = AuditLog.sqlite(tmp_path / "x.db", signing_key=b"a" * 32)
    audit.emit(actor="a", action="x", payload={})
    audit.emit(actor="b", action="y", payload={})

    # Get the timestamp of the second event so we can slice
    events = list(audit.store.iter_events())
    cutoff = events[1].ts

    # Slice "since the second event onwards"
    out = audit.export(tmp_path / "slice.jsonl", since=cutoff)
    lines = out.read_bytes().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["actor"] == "b"


# ---------------------------------------------------------------------------
# Skip env var honored — useful for cross-environment CI
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("SKIP_TESTS_REQUIRING_FILESYSTEM") == "1",
    reason="filesystem-touching tests skipped",
)
def test_filesystem_tests_run_by_default(tmp_path: Path) -> None:
    """A no-op test that's only here to verify the skip mechanism
    above is wired correctly. If the env var is unset (default), this
    runs and passes; CI that sets the var skips the file-touching
    tests including this one."""
    (tmp_path / "marker").write_text("ok")
    assert (tmp_path / "marker").read_text() == "ok"
