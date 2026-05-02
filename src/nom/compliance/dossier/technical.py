"""Đ14.1.c technical dossier (*hồ sơ kỹ thuật*) — full implementation.

A high-risk provider must keep, update, and archive a technical
dossier + operational log sufficient for conformity assessment and
post-deployment inspection. This module assembles the dossier from:

- the system spec + classification result (risk-management section
  per Đ14.1.a),
- a summary view of the audit log over a date range (operational-log
  section per Đ14.1.c),
- caller-supplied descriptions of data governance (Đ14.1.b), human
  oversight (Đ14.1.d), and incident history (Đ12).

Đ14.1.e excludes source code, detailed algorithms, parameter sets,
and trade secrets from the public surface — the dossier surfaces a
*functional description* and *main types of input data* only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from nom.compliance.dossier._render import render_template

if TYPE_CHECKING:
    from nom.compliance.audit import AuditLog
    from nom.compliance.risk import ClassificationResult, SystemSpec

__all__ = ["TechnicalDossier"]


@dataclass(frozen=True, slots=True)
class _OperationalLogSummary:
    """Reduced view of the audit log over a date window."""

    since: str
    until: str
    n_events: int
    by_actor: tuple[tuple[str, int], ...]
    by_action: tuple[tuple[str, int], ...]
    chain_verified: bool


@dataclass
class TechnicalDossier:
    spec: SystemSpec
    classification: ClassificationResult
    audit_log: AuditLog
    provider_name: str
    provider_contact: str
    functional_description: str
    """One-paragraph public-safe description (Đ14.1.e). NOT source code."""

    main_input_data_types: tuple[str, ...]
    """E.g. ("Văn bản hợp đồng PDF", "Câu hỏi tiếng Việt").
    Surface-level types only; not training-data details."""

    risk_mitigation_measures: tuple[str, ...]
    """Bullet list per Đ14.1.a — what you do to manage residual risk."""

    data_governance_notes: str
    """Paragraph per Đ14.1.b on training/validation data policy."""

    human_oversight_design: str
    """Paragraph per Đ14.1.d — how a human inspects + intervenes."""

    deployer_name: str | None = None
    deployer_contact: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_pipeline(
        cls,
        *,
        spec: SystemSpec,
        classification: ClassificationResult,
        audit_log: AuditLog,
        provider_name: str,
        provider_contact: str,
        functional_description: str,
        main_input_data_types: tuple[str, ...] | list[str],
        risk_mitigation_measures: tuple[str, ...] | list[str],
        data_governance_notes: str,
        human_oversight_design: str,
        deployer_name: str | None = None,
        deployer_contact: str | None = None,
    ) -> TechnicalDossier:
        return cls(
            spec=spec,
            classification=classification,
            audit_log=audit_log,
            provider_name=provider_name,
            provider_contact=provider_contact,
            functional_description=functional_description,
            main_input_data_types=tuple(main_input_data_types),
            risk_mitigation_measures=tuple(risk_mitigation_measures),
            data_governance_notes=data_governance_notes,
            human_oversight_design=human_oversight_design,
            deployer_name=deployer_name,
            deployer_contact=deployer_contact,
        )

    def render(
        self,
        *,
        language: Literal["vi", "en"] = "vi",
        log_since: str | None = None,
        log_until: str | None = None,
    ) -> str:
        log_summary = self._summarise_audit(since=log_since, until=log_until)
        ctx: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "law": "Luật 134/2025/QH15",
            "spec": self.spec,
            "classification": self.classification,
            "log": log_summary,
            "provider_name": self.provider_name,
            "provider_contact": self.provider_contact,
            "deployer_name": self.deployer_name,
            "deployer_contact": self.deployer_contact,
            "functional_description": self.functional_description,
            "main_input_data_types": self.main_input_data_types,
            "risk_mitigation_measures": self.risk_mitigation_measures,
            "data_governance_notes": self.data_governance_notes,
            "human_oversight_design": self.human_oversight_design,
            "extra": self.extra,
        }
        return render_template(f"technical_dossier.{language}.md.j2", ctx)

    def write(
        self,
        path: str | Path,
        *,
        language: Literal["vi", "en"] = "vi",
        log_since: str | None = None,
        log_until: str | None = None,
    ) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            self.render(language=language, log_since=log_since, log_until=log_until),
            encoding="utf-8",
        )
        return out

    def _summarise_audit(self, *, since: str | None, until: str | None) -> _OperationalLogSummary:
        n = 0
        by_actor: dict[str, int] = {}
        by_action: dict[str, int] = {}
        first_ts = ""
        last_ts = ""
        for ev in self.audit_log.store.iter_events():
            if since is not None and ev.ts < since:
                continue
            if until is not None and ev.ts > until:
                continue
            n += 1
            if not first_ts:
                first_ts = ev.ts
            last_ts = ev.ts
            by_actor[ev.actor] = by_actor.get(ev.actor, 0) + 1
            by_action[ev.action] = by_action.get(ev.action, 0) + 1
        verified = self.audit_log.verify().ok
        return _OperationalLogSummary(
            since=since or first_ts,
            until=until or last_ts,
            n_events=n,
            by_actor=tuple(sorted(by_actor.items(), key=lambda kv: -kv[1])),
            by_action=tuple(sorted(by_action.items(), key=lambda kv: -kv[1])),
            chain_verified=verified,
        )
