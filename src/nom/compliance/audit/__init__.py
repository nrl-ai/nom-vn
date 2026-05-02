"""Append-only signed audit log — Luật 134/2025 Đ14.1.c, Đ28.3.

Đ14.1.c requires a high-risk provider to "lập, cập nhật, lưu giữ hồ sơ
kỹ thuật và nhật ký hoạt động ở mức cần thiết cho việc đánh giá sự phù
hợp và kiểm tra sau khi đưa vào sử dụng." Đ28.3 obliges the same
provider to surrender that log, training data, and source info during
inspection. This submodule is what produces the *nhật ký hoạt động* —
a tamper-evident chain that an inspector can re-verify.

Default chain primitive is HMAC-SHA256 (via ``cryptography``,
Apache-2.0 / BSD-3) — same algorithm a bank's audit log would use.
``Signer`` is a Protocol; v0.4 will ship an ML-DSA-65 adapter (FIPS 204
quantum-safe) once Asqav matures past its current ~1-month track
record.

Default sink is :class:`SQLiteStore` (matches ``nom.chat.SqliteStore``).
:class:`JSONLStore` is the export-friendly variant — append-only file,
trivially streamable, what you hand to an inspector when they ask for
"the last 30 days".
"""

from __future__ import annotations

from nom.compliance.audit.event import AuditChainTamperedError, AuditEvent, VerifyResult
from nom.compliance.audit.log import AuditLog
from nom.compliance.audit.store import JSONLStore, Signer, SQLiteStore, Store

__all__ = [
    "AuditChainTamperedError",
    "AuditEvent",
    "AuditLog",
    "JSONLStore",
    "SQLiteStore",
    "Signer",
    "Store",
    "VerifyResult",
]
