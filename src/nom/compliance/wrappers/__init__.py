"""Composition wrappers — Đ14.1.c, Đ14.1.e, Đ28.3.

These wrap existing :mod:`nom.llm` / :mod:`nom.rag` instances with
audit-trail emission. The Protocol contracts of the wrapped objects
are preserved so deeper code keeps working unchanged.

This is the file most users interact with: ``AuditedLLM`` and
``AuditedRAG`` are how a deployer turns a stock pipeline into one
that logs every model call into the chain-signed
:class:`nom.compliance.AuditLog`.
"""

from __future__ import annotations

from nom.compliance.wrappers.llm import AuditedLLM
from nom.compliance.wrappers.rag import AuditedRAG

__all__ = ["AuditedLLM", "AuditedRAG"]
