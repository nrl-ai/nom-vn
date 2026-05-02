"""Registry: jurisdiction id → currently-recommended :class:`LawSpec`.

Adding a new law to nom-vn is one new module under
:mod:`nom.compliance.laws` plus one entry here. Pinning to a specific
historical version is a direct module import (e.g. ``from
nom.compliance.laws.vn_134_2025 import LAW``); the registry returns
the version the maintainers consider canonical *today*.
"""

from __future__ import annotations

from nom.compliance.laws._types import LawSpec
from nom.compliance.laws.vn_134_2025 import LAW as _VN_134_2025

__all__ = ["available", "get"]


_REGISTRY: dict[str, LawSpec] = {
    "VN-134/2025": _VN_134_2025,
}


def get(law_id: str) -> LawSpec:
    """Return the canonical :class:`LawSpec` for ``law_id``."""
    if law_id not in _REGISTRY:
        msg = (
            f"Unknown law_id={law_id!r}. Known IDs: {sorted(_REGISTRY)}. "
            "To add a law, create nom/compliance/laws/<jurisdiction>.py "
            "exporting LAW: LawSpec, and register it in laws/registry.py."
        )
        raise KeyError(msg)
    return _REGISTRY[law_id]


def available() -> tuple[str, ...]:
    """List of registered law IDs."""
    return tuple(sorted(_REGISTRY))
