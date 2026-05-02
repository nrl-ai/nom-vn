"""``AuditForwarder`` Protocol + OSS no-op default.

The canonical audit chain lives in ``nom.compliance.audit.AuditLog`` —
that's the tamper-evident, HMAC-signed ledger an inspector replays.
Forwarders are *secondary* sinks for the same events: shipping a copy
to Splunk / ELK / Loki / syslog so the SOC has live visibility, while
the chain stays the source of truth.

Decoupling reasons (why this isn't a method on ``Store``):

- Forwarding is best-effort — a network failure shouldn't break audit
  emission. The Store write must succeed atomically.
- Forwarders run async; the Store interface is sync.
- Multiple forwarders may be active (Splunk for SOC, OTel for SRE).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from nom.compliance.audit.event import AuditEvent

__all__ = ["AuditForwarder", "NoOpAuditForwarder"]


@runtime_checkable
class AuditForwarder(Protocol):
    """Ship audit events to one external sink, best-effort.

    Implementations must:
    - Not raise on transport failure (log + drop). Audit emission
      cannot be blocked by an unreachable SIEM.
    - Implement ``flush()`` for graceful shutdown.
    - Be safe to call from any thread.
    """

    name: str

    def forward(self, event: AuditEvent) -> None:
        """Best-effort ship of one event."""
        ...

    def flush(self) -> None:
        """Block until pending events are delivered or dropped."""
        ...


@dataclass
class NoOpAuditForwarder:
    """OSS default: do nothing.

    Replace with the EE Splunk / ELK / Loki / syslog forwarder by
    installing ``nom-vn-enterprise`` and registering via the
    ``nom.platform.audit_forwarders`` entry point.
    """

    name: str = "noop"

    def forward(self, event: AuditEvent) -> None:
        del event

    def flush(self) -> None:
        return
