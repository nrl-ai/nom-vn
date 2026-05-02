"""Record + classify serious incidents per Đ3.8 / Đ12.

:class:`SeriousIncident` is the frozen value an operator captures the
moment something goes wrong. :class:`IncidentRecorder` stores them
locally (default JSONL) and chain-signs each record into the audit
log so the incident timeline is tamper-evident the same way Đ14.1.c
operational logs are.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nom.compliance.audit import AuditLog

__all__ = [
    "IncidentCategory",
    "IncidentRecorder",
    "IncidentSeverity",
    "SeriousIncident",
]


class IncidentSeverity(str, Enum):
    """Operator's first-call severity. Đ12.3 lets the authority
    re-classify; this is the operator's record of what they saw."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentCategory(str, Enum):
    """The Đ3.8 harm types, modelled as a flat enum so the recorder
    can validate at construction. Multiple categories per incident
    are supported via :attr:`SeriousIncident.categories`."""

    LIFE_HEALTH = "life-health"
    HUMAN_RIGHTS = "human-rights"
    PROPERTY = "property"
    CYBERSECURITY = "cybersecurity"
    PUBLIC_ORDER = "public-order"
    ENVIRONMENT = "environment"
    NATIONAL_SECURITY_INFRA = "national-security-infra"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SeriousIncident:
    """One incident, ready to render into a Đ12.4 portal report."""

    incident_id: str
    detected_at: str
    """ISO-8601 UTC of the moment the operator detected the event."""

    severity: IncidentSeverity
    categories: tuple[IncidentCategory, ...]
    summary: str
    """One-line summary in VN — what happened and what the operator
    immediately did. Goes into the public part of the portal report."""

    system_name: str
    """Deployer-facing brand of the AI system that caused the event."""

    affected_persons_estimate: int = 0
    """Best estimate at detection time. Updates land as new
    SeriousIncident records linked via :attr:`parent_id`."""

    technical_details: str | None = None
    """Internal-only detail (stack trace, model version, input that
    triggered, etc.). The portal accepts this as a confidential
    annex."""

    parent_id: str | None = None
    """Set when this record updates an earlier incident."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass
class IncidentRecorder:
    """Append-only JSONL store for incidents + optional audit-log
    integration.

    Pass ``audit_log`` to chain each incident into the same signed
    log used for operational events (Đ14.1.c). Without it, the
    recorder still produces a usable JSONL but inspectors will only
    have the JSONL hash for tamper evidence, not the chain.
    """

    path: Path
    audit_log: AuditLog | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def record(
        self,
        *,
        severity: IncidentSeverity,
        categories: tuple[IncidentCategory, ...] | list[IncidentCategory],
        summary: str,
        system_name: str,
        affected_persons_estimate: int = 0,
        technical_details: str | None = None,
        parent_id: str | None = None,
    ) -> SeriousIncident:
        if not categories:
            msg = "record() requires at least one IncidentCategory"
            raise ValueError(msg)
        incident = SeriousIncident(
            incident_id=uuid.uuid4().hex,
            detected_at=_now_iso(),
            severity=severity,
            categories=tuple(categories),
            summary=summary,
            system_name=system_name,
            affected_persons_estimate=affected_persons_estimate,
            technical_details=technical_details,
            parent_id=parent_id,
        )
        line = json.dumps(_serialize(incident), ensure_ascii=False) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line)
        if self.audit_log is not None:
            self.audit_log.emit(
                actor=f"incident:{system_name}",
                action="incident.recorded",
                payload=_serialize(incident),
                risk_tier="high"
                if severity
                in {
                    IncidentSeverity.HIGH,
                    IncidentSeverity.CRITICAL,
                }
                else None,
                parent_id=parent_id,
            )
        return incident

    def all(self) -> list[SeriousIncident]:
        out: list[SeriousIncident] = []
        with self._lock, self.path.open("r", encoding="utf-8") as f:
            for raw in f:
                if not raw.strip():
                    continue
                data = json.loads(raw)
                out.append(_deserialize(data))
        return out


def _serialize(incident: SeriousIncident) -> dict[str, Any]:
    d = asdict(incident)
    d["severity"] = incident.severity.value
    d["categories"] = [c.value for c in incident.categories]
    return d


def _deserialize(data: dict[str, Any]) -> SeriousIncident:
    return SeriousIncident(
        incident_id=str(data["incident_id"]),
        detected_at=str(data["detected_at"]),
        severity=IncidentSeverity(data["severity"]),
        categories=tuple(IncidentCategory(c) for c in data["categories"]),
        summary=str(data["summary"]),
        system_name=str(data["system_name"]),
        affected_persons_estimate=int(data.get("affected_persons_estimate", 0)),
        technical_details=data.get("technical_details"),
        parent_id=data.get("parent_id"),
    )
