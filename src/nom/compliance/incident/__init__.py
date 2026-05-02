"""Serious incident handling — Luật 134/2025 Đ12.

Đ3.8 defines a *sự cố nghiêm trọng* (serious incident) as an event
during AI system operation that causes or risks significant harm to
life, health, human rights, property, cybersecurity, public order,
the environment, or disrupts critical national-security information
systems.

Đ12.2 obliges providers / deployers / users to record incidents
promptly and apply technical mitigation; Đ12.4 routes the formal
report through Cổng thông tin một cửa (Single-window AI Portal). The
portal URL + API are not yet published (Đ12.5 says Government will
detail) — :class:`IncidentRecorder` produces the structured report
locally so it's ready to submit when the portal goes live.
"""

from __future__ import annotations

from nom.compliance.incident.recorder import (
    IncidentCategory,
    IncidentRecorder,
    IncidentSeverity,
    SeriousIncident,
)
from nom.compliance.incident.report import incident_report_dict

__all__ = [
    "IncidentCategory",
    "IncidentRecorder",
    "IncidentSeverity",
    "SeriousIncident",
    "incident_report_dict",
]
