"""``nom.compliance`` — Vietnamese AI Law 134/2025 compliance toolkit.

This module turns a stock ``nom.rag`` / ``nom.llm`` pipeline into one
that can pass a Bộ Khoa học và Công nghệ inspection: every model call
is signed and chain-linked into a tamper-evident audit log; the system
is risk-classified per the law's three-tier framework; technical
dossiers and incident reports render to the templates inspectors expect.

The module is composed of small, swappable pieces — each addresses one
specific obligation in Law 134/2025/QH15. Wrap your existing pipeline
with :class:`AuditedRAG` / :class:`AuditedLLM`; classify with
:class:`RiskClassifier`; export evidence with
:meth:`AuditLog.export`.

Article-level mapping lives in the docstrings of each submodule. See
``docs/tasks/compliance.md`` for the user-facing guide.
"""

from __future__ import annotations

from nom.compliance.audit import (
    AuditChainTamperedError,
    AuditEvent,
    AuditLog,
    JSONLStore,
    Signer,
    SQLiteStore,
    Store,
    VerifyResult,
)
from nom.compliance.types import RiskTier

__all__ = [
    "AuditChainTamperedError",
    "AuditEvent",
    "AuditLog",
    "JSONLStore",
    "RiskTier",
    "SQLiteStore",
    "Signer",
    "Store",
    "VerifyResult",
]
