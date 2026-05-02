"""Đ27 impact assessment for state-use AI — MVP skeleton.

Đ27.3 obliges agencies operating high-risk AI (or AI with significant
impact on human rights, social fairness, public interests) to prepare
an impact-assessment report covering: risk identification, control
measures, oversight + intervention design.

Đ27.5 says Government will detail the report's content / procedure;
the implementing decree is pending. v0.3 ships a structurally
complete skeleton with the Đ27.3 fields pre-laid-out for an agency
to fill in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from nom.compliance.dossier._render import render_template

if TYPE_CHECKING:
    from nom.compliance.risk import ClassificationResult, SystemSpec

__all__ = ["ImpactAssessment"]


@dataclass(frozen=True, slots=True)
class ImpactAssessment:
    """Skeleton Đ27 impact assessment for state-use AI."""

    spec: SystemSpec
    classification: ClassificationResult
    agency_name: str
    agency_contact: str
    identified_risks: tuple[str, ...]
    control_measures: tuple[str, ...]
    oversight_design: str

    def render(self, *, language: Literal["vi"] = "vi") -> str:
        return render_template(
            f"impact_assessment.{language}.md.j2",
            {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "law": "Luật 134/2025/QH15",
                "is_mvp_skeleton": True,
                "spec": self.spec,
                "classification": self.classification,
                "agency_name": self.agency_name,
                "agency_contact": self.agency_contact,
                "identified_risks": self.identified_risks,
                "control_measures": self.control_measures,
                "oversight_design": self.oversight_design,
            },
        )

    def write(self, path: str | Path, *, language: Literal["vi"] = "vi") -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.render(language=language), encoding="utf-8")
        return out
