"""Cross-module value types for ``nom.compliance``.

Lives outside ``audit`` / ``risk`` / ``dossier`` so each submodule can
import it without circular dependencies. Add new types here only if
they're referenced by ≥2 submodules.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["RiskTier"]


class RiskTier(str, Enum):
    """Three-tier risk classification per Luật 134/2025/QH15 Đ9.1.

    Values are the legal labels themselves so an audit log entry tagged
    ``risk_tier="high"`` reads naturally to a Vietnamese inspector.

    - ``HIGH`` — Đ9.1.a: significant harm to life, health, rights,
      national interests, public interests, or national security.
    - ``MEDIUM`` — Đ9.1.b: causes confusion or manipulation when users
      cannot recognize they're interacting with AI / AI-generated
      content.
    - ``LOW`` — Đ9.1.c: everything not falling under HIGH or MEDIUM.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
