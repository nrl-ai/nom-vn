"""Đ12.4 portal-format report.

Bộ KH&CN's Cổng thông tin một cửa (Single-window AI Portal) is the
intake channel for serious-incident reports. The portal API is not
public yet (Đ12.5: Government will detail), but the report's
information surface is set by Đ12.2 and Đ3.8: who, what, when,
severity, harm categories, technical mitigation taken.

This module renders a :class:`SeriousIncident` into a stable dict
shape that maps directly onto those fields. When the portal API
publishes, a translator dict→portal-payload goes here without
breaking the public function signature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nom.compliance.incident.recorder import SeriousIncident

__all__ = ["incident_report_dict"]


def incident_report_dict(
    incident: SeriousIncident,
    *,
    provider_name: str,
    provider_contact: str,
    deployer_name: str | None = None,
    deployer_contact: str | None = None,
    mitigation_taken: str | None = None,
) -> dict[str, Any]:
    """Render an incident as a portal-ready payload.

    ``provider_name`` / ``provider_contact`` are mandatory because
    Đ14.6 requires foreign providers to maintain a VN legal contact;
    domestic providers use their company info. ``deployer_*`` is
    optional but recommended (the deployer often has more direct
    operational context).

    ``mitigation_taken`` is a one-paragraph description of the
    technical action already applied per Đ12.2.a (recall, suspend,
    fix). The portal accepts this as the public mitigation summary.
    """
    return {
        "law_reference": "VN-134/2025",
        "article": "Đ12",
        "incident": {
            "id": incident.incident_id,
            "detected_at": incident.detected_at,
            "severity": incident.severity.value,
            "categories": [c.value for c in incident.categories],
            "summary": incident.summary,
            "affected_persons_estimate": incident.affected_persons_estimate,
        },
        "system": {
            "name": incident.system_name,
        },
        "provider": {
            "name": provider_name,
            "contact": provider_contact,
        },
        "deployer": (
            {"name": deployer_name, "contact": deployer_contact}
            if deployer_name is not None or deployer_contact is not None
            else None
        ),
        "mitigation_taken": mitigation_taken,
        "technical_details": incident.technical_details,
        "parent_incident_id": incident.parent_id,
    }
