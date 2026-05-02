"""``AuditedLLM`` — drop-in replacement for any :class:`nom.llm.LLM`.

Wraps a stock LLM adapter (Ollama / OpenAI / Anthropic / llama.cpp /
HuggingFace) and chain-signs each call into the audit log. Three
events fire per call:

- ``complete`` — pre-call, payload hash + schema + max_tokens
- ``complete.ok`` — post-call success, output hash + parent_id
- ``complete.err`` — post-call exception, error message (truncated)

The Protocol contract is preserved: anything that takes an
:class:`nom.llm.LLM` accepts an ``AuditedLLM`` because they share the
same ``name`` attribute and ``complete()`` signature.

Default: payload-hashed (privacy minimization). Pass ``store_raw=True``
to retain the raw prompt + output in the audit-event payload — only
do this when the deployment sector mandates content retention (e.g.,
banking with 7-year audit rules).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nom.compliance.types import RiskTier

if TYPE_CHECKING:
    from nom.compliance.audit import AuditEvent, AuditLog
    from nom.llm.base import LLM

__all__ = ["AuditedLLM"]


@dataclass
class AuditedLLM:
    """Wrap an :class:`LLM` so every ``complete()`` is chain-logged.

    Compose with anything that takes an LLM Protocol::

        from nom.llm import Ollama
        from nom.compliance import AuditLog, AuditedLLM, RiskTier

        audit = AuditLog.sqlite("audit.db", signing_key=key)
        llm = AuditedLLM(Ollama("qwen3:8b"), audit_log=audit,
                         risk_tier=RiskTier.MEDIUM)
        # llm satisfies the LLM Protocol — pass to RAG, Extract, etc.
    """

    inner: LLM
    audit_log: AuditLog
    risk_tier: RiskTier | str | None = None
    store_raw: bool = False
    """When True, raw prompt + output text land in the audit event
    payload (not just their hashes). Privacy regulators frown on this
    by default; only enable when sector retention rules require it."""

    @property
    def name(self) -> str:
        return f"audited({self.inner.name})"

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        actor = f"llm:{self.inner.name}"
        pre_payload: dict[str, Any] = {
            "schema": schema,
            "max_tokens": max_tokens,
        }
        if self.store_raw:
            pre_payload["prompt"] = prompt
        else:
            pre_payload["prompt_len"] = len(prompt)

        pre_event = self.audit_log.emit(
            actor=actor,
            action="complete",
            payload=pre_payload,
            risk_tier=self.risk_tier,
        )

        try:
            output = self.inner.complete(prompt, schema=schema, max_tokens=max_tokens)
        except Exception as exc:
            err_payload: dict[str, Any] = {"err": str(exc)[:500]}
            self.audit_log.emit(
                actor=actor,
                action="complete.err",
                payload=err_payload,
                risk_tier=self.risk_tier,
                parent_id=pre_event.span_id,
            )
            raise

        ok_payload: dict[str, Any] = {"output_len": len(output)}
        if self.store_raw:
            ok_payload["output"] = output
        self.audit_log.emit(
            actor=actor,
            action="complete.ok",
            payload=ok_payload,
            risk_tier=self.risk_tier,
            parent_id=pre_event.span_id,
        )
        return output

    def last_event(self) -> AuditEvent | None:
        """Convenience for tests / debugging — returns the most recent
        event in the audit store."""
        return self.audit_log.store.last()
