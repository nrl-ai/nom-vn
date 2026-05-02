"""Storage sinks + signing primitive for :mod:`nom.compliance.audit`.

The :class:`Store` Protocol is the seam an enterprise can plug a
managed backend into (Postgres, BigQuery, S3 manifest); the two
in-tree implementations are what nom-vn ships out of the box.

The :class:`Signer` Protocol is the swap point for the chain primitive.
``HMACSigner`` is the default (Apache 2.0 / BSD-3 via
``cryptography``); a quantum-safe ``MLDSASigner`` adapter is planned
for v0.4 once an upstream meets the maturity bar (≥6 months track
record, ≥500 stars, security history clean).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Protocol, runtime_checkable

from nom.compliance.audit.event import AuditEvent, canonical_json

__all__ = [
    "HMACSigner",
    "JSONLStore",
    "SQLiteStore",
    "Signer",
    "Store",
]


@runtime_checkable
class Signer(Protocol):
    """Cryptographic primitive that signs each chain entry.

    The signed message is ``prev_sig || canonical_json(event_minus_sig)``.
    Verification is signer-specific: HMAC re-computes; a public-key
    signer would call ``verify``. Either way, the chain breaks if any
    entry's payload, ``prev_sig``, or ``sig`` is mutated.
    """

    name: str

    def sign(self, message: bytes) -> bytes: ...

    def verify(self, message: bytes, sig: bytes) -> bool: ...


class HMACSigner:
    """HMAC-SHA256 signer over a 32+ byte secret key.

    The key is symmetric — anyone who can verify can also forge —
    so in production the key lives in an HSM / KMS / a kernel keyring,
    and verification by an inspector means re-signing under the same
    key. Rotate by issuing a new key-id and starting a new chain (do
    NOT re-sign an old chain under a new key; that would invalidate
    its tamper-evidence).
    """

    name = "hmac-sha256"

    def __init__(self, key: bytes) -> None:
        if len(key) < 16:
            msg = "HMACSigner key must be at least 16 bytes (recommend 32+)"
            raise ValueError(msg)
        self._key = bytes(key)

    def sign(self, message: bytes) -> bytes:
        # Lazy import — `cryptography` is in the [compliance] extra,
        # not a hard dep. Importing at module top would force every
        # `import nom` to pay the cryptography cost.
        from cryptography.hazmat.primitives import hashes, hmac

        h = hmac.HMAC(self._key, hashes.SHA256())
        h.update(message)
        # h.finalize() is typed as Any in cryptography stubs; the runtime
        # contract is bytes (HMAC digest). Coerce so mypy --strict accepts.
        return bytes(h.finalize())

    def verify(self, message: bytes, sig: bytes) -> bool:
        from cryptography.hazmat.primitives import hashes, hmac

        h = hmac.HMAC(self._key, hashes.SHA256())
        h.update(message)
        try:
            h.verify(sig)
        except Exception:
            return False
        return True


@runtime_checkable
class Store(Protocol):
    """Append-only event store.

    Implementations must be safe to call from multiple threads and
    must preserve insertion order on iteration — the chain depends
    on order. Enterprise plug-ins that lose order (some columnar
    warehouses) need an indexed view that restores it.
    """

    def append(self, event: AuditEvent) -> None: ...

    def iter_events(self) -> Iterator[AuditEvent]: ...

    def last(self) -> AuditEvent | None: ...

    def close(self) -> None: ...


class SQLiteStore:
    """Default sink. One file, one schema, one writer thread.

    Concurrency: SQLite serializes writers, which is fine for the
    audit-log workload (write-heavy but never bursty — one event per
    LLM call). Multiple readers are unblocked.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS audit_events (
            row_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            span_id   TEXT NOT NULL UNIQUE,
            ts        TEXT NOT NULL,
            actor     TEXT NOT NULL,
            action    TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            risk_tier TEXT,
            parent_id TEXT,
            prev_sig  TEXT NOT NULL,
            sig       TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(ts);
        CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor);
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        # check_same_thread=False because the audit log may emit from
        # whichever thread the LLM call ran on; we serialize ourselves
        # via _lock instead of relying on SQLite's per-thread default.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(self._SCHEMA)
            self._conn.commit()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit_events "
                "(span_id, ts, actor, action, payload_hash, risk_tier, parent_id, prev_sig, sig) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.span_id,
                    event.ts,
                    event.actor,
                    event.action,
                    event.payload_hash,
                    event.risk_tier,
                    event.parent_id,
                    event.prev_sig,
                    event.sig,
                ),
            )
            self._conn.commit()

    def iter_events(self) -> Iterator[AuditEvent]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT span_id, ts, actor, action, payload_hash, risk_tier, "
                "parent_id, prev_sig, sig FROM audit_events ORDER BY row_id ASC"
            )
            rows = cur.fetchall()
        for row in rows:
            yield AuditEvent(
                span_id=row[0],
                ts=row[1],
                actor=row[2],
                action=row[3],
                payload_hash=row[4],
                risk_tier=row[5],
                parent_id=row[6],
                prev_sig=row[7],
                sig=row[8],
            )

    def last(self) -> AuditEvent | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT span_id, ts, actor, action, payload_hash, risk_tier, "
                "parent_id, prev_sig, sig FROM audit_events "
                "ORDER BY row_id DESC LIMIT 1"
            )
            row = cur.fetchone()
        if row is None:
            return None
        return AuditEvent(
            span_id=row[0],
            ts=row[1],
            actor=row[2],
            action=row[3],
            payload_hash=row[4],
            risk_tier=row[5],
            parent_id=row[6],
            prev_sig=row[7],
            sig=row[8],
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class JSONLStore:
    """Append-only newline-delimited JSON.

    Trivially streamable — what you hand an inspector when they ask
    for "the last 30 days". One event per line, canonical-JSON encoded
    so a re-hash matches the original.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # Touch the file so iter_events on a fresh log doesn't error.
        self._path.touch(exist_ok=True)

    def append(self, event: AuditEvent) -> None:
        line = canonical_json(asdict(event)) + b"\n"
        with self._lock, self._path.open("ab") as f:
            f.write(line)

    def iter_events(self) -> Iterator[AuditEvent]:
        with self._lock, self._path.open("rb") as f:
            data = f.read()
        for raw in data.splitlines():
            if not raw.strip():
                continue
            obj = json.loads(raw)
            yield AuditEvent(**obj)

    def last(self) -> AuditEvent | None:
        last_event: AuditEvent | None = None
        for event in self.iter_events():
            last_event = event
        return last_event

    def close(self) -> None:  # nothing to close
        return
