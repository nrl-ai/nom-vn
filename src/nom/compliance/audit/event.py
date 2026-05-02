"""Frozen value types for the audit chain — no runtime side effects.

Lives in a separate module so :mod:`nom.compliance.audit.store` and
:mod:`nom.compliance.audit.log` can both depend on it without a
circular import.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

__all__ = [
    "AuditChainTamperedError",
    "AuditEvent",
    "VerifyResult",
    "canonical_json",
]


def canonical_json(obj: object) -> bytes:
    """Deterministic JSON encoding for hashing.

    Sorted keys, no whitespace, ``ensure_ascii=False`` so VN/CJK text
    hashes the same on every platform. Identical input → identical
    bytes → identical signature; this is the property the chain
    relies on.
    """
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One row in the audit chain — frozen, signed, replayable.

    Field order matters: it's the canonical layout used to compute
    ``sig``. Don't reorder without bumping the chain format version.
    """

    span_id: str
    ts: str
    actor: str
    action: str
    payload_hash: str
    risk_tier: str | None
    parent_id: str | None
    prev_sig: str
    sig: str

    def to_signing_payload(self) -> dict[str, Any]:
        """Subset of fields that get signed (everything except ``sig``)."""
        d = asdict(self)
        d.pop("sig", None)
        return d


@dataclass(frozen=True, slots=True)
class VerifyResult:
    """Outcome of replaying a chain.

    ``ok=True`` means every signature verified and ``prev_sig`` linkages
    are consistent. Otherwise ``failed_at`` points at the first event
    whose signature didn't validate (the earliest tampered row).
    """

    ok: bool
    n_events: int
    failed_at: str | None = None
    failure_reason: str | None = None

    def raise_if_tampered(self) -> None:
        if not self.ok:
            msg = (
                f"Audit chain tampered: {self.failure_reason} "
                f"(failed_at={self.failed_at}, n_events={self.n_events})"
            )
            raise AuditChainTamperedError(msg)


class AuditChainTamperedError(RuntimeError):
    """Raised when :meth:`VerifyResult.raise_if_tampered` finds a break."""
