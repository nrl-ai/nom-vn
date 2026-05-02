"""``AuditedRAG`` — wraps :class:`nom.rag.RAG` so ``ask()`` is chain-logged.

Three events fire per ask:

- ``rag.ask`` — pre-call, question hash + retrieval params
- ``rag.ask.ok`` — post-call, answer hash + n_citations + citation
  scores (no raw chunk text by default)
- ``rag.ask.err`` — exception path

Citations are recorded as ``(doc_idx, chunk_idx, score)`` tuples — the
same shape :class:`nom.rag.Answer.citations` returns. This is the
"which chunks the model saw" record an inspector wants under Đ14.1.e
(explainability of input data).

Composition pattern (vs. subclass): we don't inherit from RAG because
``RAG.from_documents`` is a class method that constructs a concrete
RAG. Wrapping by composition keeps construction unchanged: build a
plain RAG, then wrap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nom.compliance.types import RiskTier

if TYPE_CHECKING:
    from nom.compliance.audit import AuditLog
    from nom.rag.pipeline import RAG, Answer

__all__ = ["AuditedRAG"]


@dataclass
class AuditedRAG:
    """Wrap a :class:`nom.rag.RAG` so every ``ask()`` is chain-logged.

    Use after constructing the RAG normally::

        rag = RAG.from_documents(["contracts/*.pdf"], llm=audited_llm)
        rag = AuditedRAG(rag, audit_log=audit, risk_tier=RiskTier.HIGH)
        ans = rag.ask("Có bao nhiêu hợp đồng có phạt vi phạm?")

    Pair with :class:`AuditedLLM` for full coverage: AuditedRAG records
    the rag-level operation; AuditedLLM records each individual model
    call inside the rag (HyDE rewrites, multi-query expansions, the
    final answer-generation call).
    """

    inner: RAG
    audit_log: AuditLog
    risk_tier: RiskTier | str | None = None
    store_raw: bool = False
    """When True, raw question + answer text land in the audit event
    payload."""

    def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        query_strategy: str = "direct",
        n_queries: int = 3,
        rerank: bool = False,
        rerank_candidates: int = 30,
        rerank_keep: int | None = None,
    ) -> Answer:
        actor = "rag:ask"
        pre_payload: dict[str, Any] = {
            "query_strategy": query_strategy,
            "top_k": top_k,
            "rerank": rerank,
            "n_queries": n_queries if query_strategy == "multi_query" else None,
        }
        if self.store_raw:
            pre_payload["question"] = question
        else:
            pre_payload["question_len"] = len(question)

        pre_event = self.audit_log.emit(
            actor=actor,
            action="ask",
            payload=pre_payload,
            risk_tier=self.risk_tier,
        )

        try:
            answer = self.inner.ask(
                question,
                top_k=top_k,
                query_strategy=query_strategy,
                n_queries=n_queries,
                rerank=rerank,
                rerank_candidates=rerank_candidates,
                rerank_keep=rerank_keep,
            )
        except Exception as exc:
            self.audit_log.emit(
                actor=actor,
                action="ask.err",
                payload={"err": str(exc)[:500]},
                risk_tier=self.risk_tier,
                parent_id=pre_event.span_id,
            )
            raise

        # Citation shape varies by Answer impl; coerce to the
        # (doc_idx, chunk_idx, score) tuples we document.
        citation_records: list[tuple[Any, Any, float]] = []
        for c in getattr(answer, "citations", ()) or ():
            doc_idx = getattr(c, "doc_idx", None)
            chunk_idx = getattr(c, "chunk_idx", None)
            score = float(getattr(c, "score", 0.0) or 0.0)
            citation_records.append((doc_idx, chunk_idx, score))

        ok_payload: dict[str, Any] = {
            "n_citations": len(citation_records),
            "citations": citation_records,
            "answer_len": len(getattr(answer, "text", "") or ""),
        }
        if self.store_raw:
            ok_payload["answer"] = getattr(answer, "text", "")
        self.audit_log.emit(
            actor=actor,
            action="ask.ok",
            payload=ok_payload,
            risk_tier=self.risk_tier,
            parent_id=pre_event.span_id,
        )
        return answer
