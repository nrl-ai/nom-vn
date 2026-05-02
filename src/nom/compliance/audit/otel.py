"""OTel span helper for compliance events.

Reuses the existing tracer + no-op fallback in
:mod:`nom.chat.observability` so a single OTel pipeline ships every
trace — chat-side spans, RAG retrieval, and now compliance audit
events all carry the same OpenInference attributes plus a few
``compliance.*`` keys an auditor can filter on.

Calling these helpers is safe whether OTel is installed or not; when
the user hasn't opted into ``[otel]`` extra the underlying tracer is a
no-op and span attributes go nowhere.
"""

from __future__ import annotations

from typing import Any

from nom.chat.observability import get_tracer

__all__ = ["annotate_audit_span", "audit_span"]


def audit_span(name: str) -> Any:
    """Open a compliance span. Use as a context manager.

    Example::

        with audit_span("rag.ask") as span:
            annotate_audit_span(span, actor="rag", action="ask",
                                 risk_tier="medium")
            ...
    """
    return get_tracer().start_as_current_span(name)


def annotate_audit_span(
    span: Any,
    *,
    actor: str,
    action: str,
    risk_tier: str | None = None,
    payload_hash: str | None = None,
    audit_event_id: str | None = None,
) -> None:
    """Tag an OTel span with ``compliance.*`` attributes.

    The keys are kept short and namespaced so an auditor's trace search
    (``compliance.actor:rag``, ``compliance.risk_tier:high``) returns
    only what it should.
    """
    try:
        span.set_attribute("compliance.actor", actor)
        span.set_attribute("compliance.action", action)
        if risk_tier is not None:
            span.set_attribute("compliance.risk_tier", risk_tier)
        if payload_hash is not None:
            span.set_attribute("compliance.payload_hash", payload_hash)
        if audit_event_id is not None:
            span.set_attribute("compliance.audit_event_id", audit_event_id)
    except Exception:  # pragma: no cover - tracer always cooperates
        # Defensive — observability never breaks the request path.
        pass
