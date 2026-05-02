"""Đ13 conformity assessment package — MVP skeleton.

Đ13.4 says the Prime Minister publishes the *Danh mục* (mandatory
list) of high-risk AI systems requiring pre-deployment certification
by a registered conformity-assessment organisation. The list isn't
published yet, so v0.3 ships a structurally complete skeleton useful
for self-assessment under Đ25.1 (free SME tool).

When the Danh mục publishes, the skeleton becomes a full dossier
with sector-specific evidence sections.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from nom.compliance.dossier._render import render_template

if TYPE_CHECKING:
    from nom.compliance.risk import ClassificationResult, SystemSpec

__all__ = ["ConformityPackage"]


@dataclass(frozen=True, slots=True)
class ConformityPackage:
    """Skeleton conformity package for self-assessment under Đ25.1.

    Sections covered today: cover, system identity, classification,
    declared mitigation, declared monitoring, declarations / sign-off
    placeholders. Sections deferred until Đ13.4 publishes: sector
    test evidence, registered organisation cross-check, certificate
    serial.
    """

    spec: SystemSpec
    classification: ClassificationResult
    provider_name: str
    provider_contact: str
    declared_mitigation_summary: str
    declared_monitoring_summary: str

    def render(self, *, language: Literal["vi"] = "vi") -> str:
        # English template lands once the Danh mục publishes; until
        # then the dossier serves a Vietnamese SME audience under
        # Đ25.1, so VN-only is sufficient for v0.3.
        return render_template(
            f"conformity_package.{language}.md.j2",
            {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "law": "Luật 134/2025/QH15",
                "is_mvp_skeleton": True,
                "spec": self.spec,
                "classification": self.classification,
                "provider_name": self.provider_name,
                "provider_contact": self.provider_contact,
                "declared_mitigation_summary": self.declared_mitigation_summary,
                "declared_monitoring_summary": self.declared_monitoring_summary,
            },
        )

    def write(self, path: str | Path, *, language: Literal["vi"] = "vi") -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.render(language=language), encoding="utf-8")
        return out
