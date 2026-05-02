"""``AuditLog`` — the chain primitive for ``nom.compliance.audit``.

Each :class:`AuditEvent` is a frozen value carrying:

- *span_id*: stable per-event UUID.
- *ts*: ISO 8601 UTC timestamp.
- *actor* / *action* / *payload_hash*: what happened.
- *risk_tier*: optional label per Đ9.1.
- *parent_id*: optional pointer for nested operations
  (``rag.ask`` is the parent of N ``llm.complete`` events).
- *prev_sig* + *sig*: HMAC-SHA256 chain.

``sig`` is computed over ``prev_sig || canonical_json(event_minus_sig)``.
Tampering with any field invalidates the entry's own ``sig`` AND every
``sig`` that follows it — the chain is what the inspector verifies.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from nom.compliance.audit.event import (
    AuditChainTamperedError,
    AuditEvent,
    VerifyResult,
    canonical_json,
)
from nom.compliance.audit.store import HMACSigner, JSONLStore, Signer, SQLiteStore, Store

if TYPE_CHECKING:
    from nom.compliance.types import RiskTier

__all__ = ["AuditChainTamperedError", "AuditEvent", "AuditLog", "VerifyResult"]


# Genesis previous-signature: 32 NUL bytes hex-encoded. Concrete value
# (vs. None) so canonical_json hashes are stable across the chain.
_GENESIS_PREV_SIG = "00" * 32


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sha256_hex(payload: object) -> str:
    """Hash a payload by canonical-JSON-encoding then SHA256.

    Returns hex so the result is stable across JSONL/SQLite round-trips
    (binary blobs in JSONL are awkward; hex is the lowest-friction
    encoding for a 32-byte digest).
    """
    return hashlib.sha256(canonical_json(payload)).hexdigest()


@dataclass
class AuditLog:
    """Append + verify + export the chain.

    Don't construct directly; use the class methods :meth:`sqlite` /
    :meth:`jsonl` for the common cases, or pass any :class:`Store` +
    :class:`Signer` for a custom backend.
    """

    store: Store
    signer: Signer
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def sqlite(
        cls,
        path: str | Path,
        *,
        signing_key: bytes,
        signer: Signer | None = None,
    ) -> AuditLog:
        """Default sink. SQLite at ``path`` + HMAC-SHA256 over
        ``signing_key`` (or any custom signer)."""
        return cls(
            store=SQLiteStore(path),
            signer=signer if signer is not None else HMACSigner(signing_key),
        )

    @classmethod
    def jsonl(
        cls,
        path: str | Path,
        *,
        signing_key: bytes,
        signer: Signer | None = None,
    ) -> AuditLog:
        """Append-only NDJSON sink."""
        return cls(
            store=JSONLStore(path),
            signer=signer if signer is not None else HMACSigner(signing_key),
        )

    def emit(
        self,
        *,
        actor: str,
        action: str,
        payload: object,
        risk_tier: RiskTier | str | None = None,
        parent_id: str | None = None,
    ) -> AuditEvent:
        """Append a signed event and return it.

        ``payload`` is hashed (not stored). Pass the prompt or output
        text directly; the canonical-JSON encoder handles VN/CJK
        correctly. If you need raw retention (banking 7-year rules),
        store the raw payload in your own system and reference it via
        the ``payload_hash`` returned here.
        """
        with self._lock:
            prev = self.store.last()
            prev_sig = prev.sig if prev is not None else _GENESIS_PREV_SIG

            tier_str: str | None
            if risk_tier is None:
                tier_str = None
            else:
                # RiskTier is a (str, Enum) — str(member) is "RiskTier.HIGH",
                # but member.value (== "high") is what we want stored. Plain
                # strings are passed through unchanged.
                tier_str = risk_tier.value if isinstance(risk_tier, Enum) else str(risk_tier)

            unsigned = {
                "span_id": uuid.uuid4().hex,
                "ts": _now_utc_iso(),
                "actor": actor,
                "action": action,
                "payload_hash": _sha256_hex(payload),
                "risk_tier": tier_str,
                "parent_id": parent_id,
                "prev_sig": prev_sig,
            }
            sig_bytes = self.signer.sign(canonical_json(unsigned))
            event = AuditEvent(
                span_id=str(unsigned["span_id"]),
                ts=str(unsigned["ts"]),
                actor=str(unsigned["actor"]),
                action=str(unsigned["action"]),
                payload_hash=str(unsigned["payload_hash"]),
                risk_tier=tier_str,
                parent_id=parent_id,
                prev_sig=str(unsigned["prev_sig"]),
                sig=sig_bytes.hex(),
            )
            self.store.append(event)
            return event

    def verify(self) -> VerifyResult:
        """Replay the chain. Returns OK or points at the first break.

        This is what an inspector runs (or what your CI runs nightly).
        Cost is O(n) over events; on a 1M-event log it's still under
        a minute on a laptop because HMAC-SHA256 is fast.
        """
        n = 0
        prev_sig = _GENESIS_PREV_SIG
        with self._lock:
            for event in self.store.iter_events():
                n += 1
                if event.prev_sig != prev_sig:
                    return VerifyResult(
                        ok=False,
                        n_events=n,
                        failed_at=event.span_id,
                        failure_reason=(
                            f"prev_sig mismatch (got {event.prev_sig[:16]}…, "
                            f"expected {prev_sig[:16]}…)"
                        ),
                    )
                signing_msg = canonical_json(event.to_signing_payload())
                if not self.signer.verify(signing_msg, bytes.fromhex(event.sig)):
                    return VerifyResult(
                        ok=False,
                        n_events=n,
                        failed_at=event.span_id,
                        failure_reason="signature mismatch",
                    )
                prev_sig = event.sig
        return VerifyResult(ok=True, n_events=n)

    def export(
        self,
        path: str | Path,
        *,
        since: str | None = None,
        until: str | None = None,
        fmt: Literal["jsonl"] = "jsonl",
    ) -> Path:
        """Write a date-bounded slice of the chain to ``path``.

        Output format is JSONL (one event per line, canonical JSON).
        ``since`` / ``until`` are ISO 8601 strings compared
        lexicographically — works because :func:`_now_utc_iso` always
        produces UTC ISO with millisecond precision.

        Đ28.3 expects ``hồ sơ kỹ thuật, nhật ký lưu vết, dữ liệu huấn
        luyện và thông tin cần thiết khác`` on demand. This is the
        ``nhật ký lưu vết`` slice; the technical dossier subsumes the
        rest.
        """
        if fmt != "jsonl":
            msg = f"export fmt={fmt!r} not supported in v0.3 (only 'jsonl')"
            raise ValueError(msg)
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, out.open("wb") as f:
            for event in self.store.iter_events():
                if since is not None and event.ts < since:
                    continue
                if until is not None and event.ts > until:
                    continue
                f.write(canonical_json(asdict(event)))
                f.write(b"\n")
        return out

    def close(self) -> None:
        with self._lock:
            self.store.close()
