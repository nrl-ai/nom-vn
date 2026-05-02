"""Tests for ``nom.compliance.audit``.

Coverage:
- Append-emit-verify round trip on both SQLite and JSONL sinks.
- Chain integrity: a tamper anywhere breaks ``verify()`` cleanly.
- HMAC primitive: short keys rejected; verify() distinguishes valid
  vs. invalid signatures.
- Canonical-JSON: VN/CJK input hashes deterministically.
- Multi-thread emit doesn't corrupt the chain.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from nom.compliance import (
    AuditEvent,
    AuditLog,
    JSONLStore,
    RiskTier,
    SQLiteStore,
)
from nom.compliance.audit.event import AuditChainTamperedError, canonical_json
from nom.compliance.audit.store import HMACSigner


@pytest.fixture
def signing_key() -> bytes:
    return b"a" * 32


@pytest.fixture
def sqlite_log(tmp_path: Path, signing_key: bytes) -> AuditLog:
    return AuditLog.sqlite(tmp_path / "audit.db", signing_key=signing_key)


@pytest.fixture
def jsonl_log(tmp_path: Path, signing_key: bytes) -> AuditLog:
    return AuditLog.jsonl(tmp_path / "audit.jsonl", signing_key=signing_key)


# ---------------------------------------------------------------------------
# canonical_json — deterministic across platforms / VN-CJK input
# ---------------------------------------------------------------------------


def test_canonical_json_deterministic_keys() -> None:
    a = canonical_json({"b": 2, "a": 1})
    b = canonical_json({"a": 1, "b": 2})
    assert a == b
    assert a == b'{"a":1,"b":2}'


def test_canonical_json_preserves_vn_unicode() -> None:
    payload = {"q": "Hợp đồng số HD-001 có điều khoản phạt vi phạm không?"}
    out = canonical_json(payload)
    # ensure_ascii=False — VN chars round-trip as themselves, not \u escapes
    assert "Hợp đồng" in out.decode("utf-8")
    # Re-encode is byte-identical
    assert canonical_json(payload) == out


# ---------------------------------------------------------------------------
# HMACSigner — short keys rejected; sign/verify roundtrip
# ---------------------------------------------------------------------------


def test_hmac_signer_rejects_short_key() -> None:
    with pytest.raises(ValueError, match="at least 16 bytes"):
        HMACSigner(b"short")


def test_hmac_signer_sign_verify_roundtrip(signing_key: bytes) -> None:
    s = HMACSigner(signing_key)
    msg = b"hello"
    sig = s.sign(msg)
    assert s.verify(msg, sig) is True
    assert s.verify(b"goodbye", sig) is False
    assert s.verify(msg, b"\x00" * len(sig)) is False


# ---------------------------------------------------------------------------
# Append + verify round trip
# ---------------------------------------------------------------------------


def test_emit_returns_event_with_signature(sqlite_log: AuditLog) -> None:
    event = sqlite_log.emit(
        actor="llm:ollama:qwen3:8b",
        action="complete",
        payload={"prompt": "Hello"},
        risk_tier=RiskTier.MEDIUM,
    )
    assert event.actor == "llm:ollama:qwen3:8b"
    assert event.action == "complete"
    assert event.risk_tier == "medium"
    assert len(event.sig) == 64  # HMAC-SHA256 = 32 bytes hex = 64 chars
    assert event.prev_sig == "00" * 32  # genesis


def test_emit_chains_prev_sig(sqlite_log: AuditLog) -> None:
    e1 = sqlite_log.emit(actor="a", action="x", payload={})
    e2 = sqlite_log.emit(actor="b", action="y", payload={})
    assert e2.prev_sig == e1.sig
    assert e1.prev_sig == "00" * 32


def test_verify_clean_chain_sqlite(sqlite_log: AuditLog) -> None:
    for i in range(20):
        sqlite_log.emit(actor=f"a{i}", action="x", payload={"i": i})
    result = sqlite_log.verify()
    assert result.ok is True
    assert result.n_events == 20
    assert result.failed_at is None


def test_verify_clean_chain_jsonl(jsonl_log: AuditLog) -> None:
    for i in range(20):
        jsonl_log.emit(actor=f"a{i}", action="x", payload={"i": i})
    result = jsonl_log.verify()
    assert result.ok is True
    assert result.n_events == 20


def test_risk_tier_serializes_to_string(sqlite_log: AuditLog) -> None:
    sqlite_log.emit(actor="a", action="x", payload={}, risk_tier=RiskTier.HIGH)
    last = sqlite_log.store.last()
    assert last is not None
    assert last.risk_tier == "high"


def test_risk_tier_none(sqlite_log: AuditLog) -> None:
    sqlite_log.emit(actor="a", action="x", payload={}, risk_tier=None)
    last = sqlite_log.store.last()
    assert last is not None
    assert last.risk_tier is None


def test_parent_id_chains_nested_operations(sqlite_log: AuditLog) -> None:
    parent = sqlite_log.emit(actor="rag", action="ask", payload={"q": "Hi"})
    child = sqlite_log.emit(
        actor="llm:ollama", action="complete", payload={"p": "Hi"}, parent_id=parent.span_id
    )
    assert child.parent_id == parent.span_id


# ---------------------------------------------------------------------------
# Tamper detection — flip a byte → verify() points at the failure
# ---------------------------------------------------------------------------


def test_tamper_payload_breaks_chain(tmp_path: Path, signing_key: bytes) -> None:
    db_path = tmp_path / "audit.db"
    log = AuditLog.sqlite(db_path, signing_key=signing_key)
    for i in range(5):
        log.emit(actor=f"a{i}", action="x", payload={"i": i})
    log.close()

    # Tamper: change the payload_hash of row 3 directly in SQLite.
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE audit_events SET payload_hash = 'deadbeef' WHERE row_id = 3")
    conn.commit()
    conn.close()

    log2 = AuditLog.sqlite(db_path, signing_key=signing_key)
    result = log2.verify()
    assert result.ok is False
    assert result.failure_reason is not None
    assert "signature" in result.failure_reason


def test_tamper_prev_sig_breaks_chain(tmp_path: Path, signing_key: bytes) -> None:
    db_path = tmp_path / "audit.db"
    log = AuditLog.sqlite(db_path, signing_key=signing_key)
    for i in range(5):
        log.emit(actor=f"a{i}", action="x", payload={"i": i})
    log.close()

    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE audit_events SET prev_sig = '00' WHERE row_id = 3")
    conn.commit()
    conn.close()

    log2 = AuditLog.sqlite(db_path, signing_key=signing_key)
    result = log2.verify()
    assert result.ok is False
    assert result.failed_at is not None


def test_tamper_jsonl_flipped_byte(tmp_path: Path, signing_key: bytes) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog.jsonl(path, signing_key=signing_key)
    for i in range(5):
        log.emit(actor=f"a{i}", action="x", payload={"i": i})

    raw = path.read_bytes()
    # Flip a byte in the middle line — has to land on a JSON-valid char
    # so the line still parses; verify() catches the chain break.
    lines = raw.splitlines()
    assert len(lines) == 5
    target = json.loads(lines[2])
    target["actor"] = "TAMPERED"
    lines[2] = canonical_json(target)
    path.write_bytes(b"\n".join(lines) + b"\n")

    log2 = AuditLog.jsonl(path, signing_key=signing_key)
    assert log2.verify().ok is False


def test_raise_if_tampered_raises(tmp_path: Path, signing_key: bytes) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog.jsonl(path, signing_key=signing_key)
    for i in range(3):
        log.emit(actor=f"a{i}", action="x", payload={"i": i})

    raw = path.read_bytes()
    lines = raw.splitlines()
    target = json.loads(lines[1])
    target["actor"] = "TAMPERED"
    lines[1] = canonical_json(target)
    path.write_bytes(b"\n".join(lines) + b"\n")

    log2 = AuditLog.jsonl(path, signing_key=signing_key)
    with pytest.raises(AuditChainTamperedError):
        log2.verify().raise_if_tampered()


def test_wrong_key_fails_verify(tmp_path: Path, signing_key: bytes) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog.jsonl(path, signing_key=signing_key)
    log.emit(actor="a", action="x", payload={})
    log.emit(actor="b", action="y", payload={})

    log_wrong = AuditLog.jsonl(path, signing_key=b"b" * 32)
    assert log_wrong.verify().ok is False


# ---------------------------------------------------------------------------
# Export — date-bounded slice
# ---------------------------------------------------------------------------


def test_export_full_chain(sqlite_log: AuditLog, tmp_path: Path) -> None:
    for i in range(10):
        sqlite_log.emit(actor=f"a{i}", action="x", payload={"i": i})
    out = sqlite_log.export(tmp_path / "export.jsonl")
    lines = out.read_bytes().splitlines()
    assert len(lines) == 10
    # Each line is a canonical-JSON event
    first = json.loads(lines[0])
    assert "sig" in first
    assert "prev_sig" in first


def test_export_unsupported_format(sqlite_log: AuditLog, tmp_path: Path) -> None:
    sqlite_log.emit(actor="a", action="x", payload={})
    with pytest.raises(ValueError, match="not supported"):
        sqlite_log.export(tmp_path / "x.parquet", fmt="parquet")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Concurrent emit — chain stays linear
# ---------------------------------------------------------------------------


def test_concurrent_emit_preserves_chain(tmp_path: Path, signing_key: bytes) -> None:
    log = AuditLog.sqlite(tmp_path / "audit.db", signing_key=signing_key)

    def worker(worker_id: int) -> None:
        for j in range(50):
            log.emit(actor=f"w{worker_id}", action="x", payload={"j": j})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    result = log.verify()
    assert result.ok is True
    assert result.n_events == 200


# ---------------------------------------------------------------------------
# AuditEvent — frozen, signing payload excludes sig
# ---------------------------------------------------------------------------


def test_audit_event_frozen() -> None:
    event = AuditEvent(
        span_id="x",
        ts="2026-05-02T00:00:00.000000Z",
        actor="a",
        action="b",
        payload_hash="0" * 64,
        risk_tier=None,
        parent_id=None,
        prev_sig="0" * 64,
        sig="1" * 64,
    )
    with pytest.raises(AttributeError):
        event.actor = "changed"  # type: ignore[misc]


def test_audit_event_signing_payload_excludes_sig() -> None:
    event = AuditEvent(
        span_id="x",
        ts="2026-05-02T00:00:00.000000Z",
        actor="a",
        action="b",
        payload_hash="0" * 64,
        risk_tier="low",
        parent_id=None,
        prev_sig="0" * 64,
        sig="1" * 64,
    )
    payload = event.to_signing_payload()
    assert "sig" not in payload
    assert payload["actor"] == "a"


# ---------------------------------------------------------------------------
# Stores — Protocol implementations work standalone
# ---------------------------------------------------------------------------


def test_sqlite_store_iter_preserves_order(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "x.db")
    for i in range(5):
        store.append(
            AuditEvent(
                span_id=f"id-{i}",
                ts=f"2026-05-02T00:00:0{i}.000000Z",
                actor=f"a{i}",
                action="x",
                payload_hash="0" * 64,
                risk_tier=None,
                parent_id=None,
                prev_sig="0" * 64,
                sig=f"{i:064x}",
            )
        )
    actors = [e.actor for e in store.iter_events()]
    assert actors == ["a0", "a1", "a2", "a3", "a4"]
    last = store.last()
    assert last is not None
    assert last.actor == "a4"


def test_jsonl_store_empty_iter(tmp_path: Path) -> None:
    store = JSONLStore(tmp_path / "x.jsonl")
    assert list(store.iter_events()) == []
    assert store.last() is None
