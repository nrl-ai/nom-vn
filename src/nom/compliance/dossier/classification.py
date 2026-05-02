"""Đ10 classification dossier — accompanies pre-deployment notification.

Đ10.3 obliges the provider to notify Bộ KH&CN of medium / high-risk
classification *before* deployment, with a *hồ sơ phân loại* attached.
This module renders that dossier from a :class:`SystemSpec` +
:class:`ClassificationResult`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from nom.compliance.dossier._render import render_template

if TYPE_CHECKING:
    from nom.compliance.risk import ClassificationResult, SystemSpec

__all__ = ["ClassificationDossier"]


@dataclass(frozen=True, slots=True)
class ClassificationDossier:
    """The Đ10 classification dossier as a renderable value.

    Construct via :meth:`from_classification` — that pulls the spec
    fields into a context dict the templates expect.
    """

    spec: SystemSpec
    classification: ClassificationResult
    provider_name: str
    provider_contact: str
    deployer_name: str | None = None
    deployer_contact: str | None = None

    @classmethod
    def from_classification(
        cls,
        *,
        spec: SystemSpec,
        classification: ClassificationResult,
        provider_name: str,
        provider_contact: str,
        deployer_name: str | None = None,
        deployer_contact: str | None = None,
    ) -> ClassificationDossier:
        return cls(
            spec=spec,
            classification=classification,
            provider_name=provider_name,
            provider_contact=provider_contact,
            deployer_name=deployer_name,
            deployer_contact=deployer_contact,
        )

    def render(self, *, language: Literal["vi", "en"] = "vi") -> str:
        """Render the dossier as a Markdown string."""
        template_name = f"classification.{language}.md.j2"
        return render_template(
            template_name,
            self._context(),
        )

    def write(self, path: str | Path, *, language: Literal["vi", "en"] = "vi") -> Path:
        """Write the rendered dossier to ``path``."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.render(language=language), encoding="utf-8")
        return out

    def _context(self) -> dict[str, object]:
        return {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "law": "Luật 134/2025/QH15",
            "spec": self.spec,
            "classification": self.classification,
            "provider_name": self.provider_name,
            "provider_contact": self.provider_contact,
            "deployer_name": self.deployer_name,
            "deployer_contact": self.deployer_contact,
        }
