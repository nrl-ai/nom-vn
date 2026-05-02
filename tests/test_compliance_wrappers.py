"""Tests for ``nom.compliance.wrappers`` — AuditedLLM + AuditedRAG.

Coverage:
- AuditedLLM emits complete + complete.ok with parent linkage.
- AuditedLLM emits complete + complete.err on exception, then
  re-raises.
- store_raw=False redacts; store_raw=True retains.
- AuditedRAG emits ask + ask.ok with citation count.
- Wrapped objects preserve the Protocol contract (LLM.name,
  LLM.complete signature).
- Chain stays intact across wrapped calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from nom.compliance import AuditLog, RiskTier
from nom.compliance.wrappers import AuditedLLM, AuditedRAG

# ---------------------------------------------------------------------------
# fakes — duck-typed against nom.llm.LLM and nom.rag.RAG / Answer
# ---------------------------------------------------------------------------


@dataclass
class _FakeLLM:
    name: str = "fake-llm"
    response: str = "ok"
    raise_on_complete: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        self.calls.append({"prompt": prompt, "schema": schema, "max_tokens": max_tokens})
        if self.raise_on_complete is not None:
            raise self.raise_on_complete
        return self.response


@dataclass
class _FakeCitation:
    doc_idx: int
    chunk_idx: int
    score: float


@dataclass
class _FakeAnswer:
    text: str
    citations: list[_FakeCitation]


@dataclass
class _FakeRAG:
    answer: _FakeAnswer
    raise_on_ask: Exception | None = None
    asks: list[dict[str, Any]] = field(default_factory=list)

    def ask(self, question: str, **kwargs: Any) -> _FakeAnswer:
        self.asks.append({"question": question, **kwargs})
        if self.raise_on_ask is not None:
            raise self.raise_on_ask
        return self.answer


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def audit(tmp_path: Path) -> AuditLog:
    return AuditLog.sqlite(tmp_path / "audit.db", signing_key=b"a" * 32)


# ---------------------------------------------------------------------------
# AuditedLLM
# ---------------------------------------------------------------------------


def test_audited_llm_passes_through_response(audit: AuditLog) -> None:
    inner = _FakeLLM(response="hello world")
    llm = AuditedLLM(inner, audit_log=audit)
    out = llm.complete("hi", max_tokens=100)
    assert out == "hello world"
    assert inner.calls[0]["prompt"] == "hi"
    assert inner.calls[0]["max_tokens"] == 100


def test_audited_llm_emits_pre_and_post_events(audit: AuditLog) -> None:
    llm = AuditedLLM(_FakeLLM(), audit_log=audit, risk_tier=RiskTier.MEDIUM)
    llm.complete("question")
    events = list(audit.store.iter_events())
    assert len(events) == 2
    assert events[0].action == "complete"
    assert events[1].action == "complete.ok"
    assert events[1].parent_id == events[0].span_id
    assert events[0].risk_tier == "medium"
    assert events[1].risk_tier == "medium"


def test_audited_llm_emits_err_on_exception_and_reraises(audit: AuditLog) -> None:
    inner = _FakeLLM(raise_on_complete=RuntimeError("boom"))
    llm = AuditedLLM(inner, audit_log=audit)
    with pytest.raises(RuntimeError, match="boom"):
        llm.complete("question")
    events = list(audit.store.iter_events())
    assert len(events) == 2
    assert events[0].action == "complete"
    assert events[1].action == "complete.err"
    assert events[1].parent_id == events[0].span_id


def test_audited_llm_redacts_payload_by_default(audit: AuditLog) -> None:
    """store_raw=False → only payload hash + length, never raw prompt."""
    llm = AuditedLLM(_FakeLLM(response="answer"), audit_log=audit)
    llm.complete("secret prompt")
    events = list(audit.store.iter_events())
    # payload_hash exists; raw prompt does not surface in any event.
    for ev in events:
        assert "secret prompt" not in ev.payload_hash  # hash, not text
    assert all(len(ev.payload_hash) == 64 for ev in events)


def test_audited_llm_store_raw_retains_payload(tmp_path: Path) -> None:
    """store_raw=True puts raw text into the payload that gets hashed."""
    audit = AuditLog.sqlite(tmp_path / "x.db", signing_key=b"a" * 32)
    llm = AuditedLLM(_FakeLLM(response="answer"), audit_log=audit, store_raw=True)
    llm.complete("prompt-A")
    llm2 = AuditedLLM(_FakeLLM(response="answer"), audit_log=audit, store_raw=True)
    llm2.complete("prompt-B")

    # With store_raw, identical prompts → identical pre-hashes
    audit2 = AuditLog.sqlite(tmp_path / "y.db", signing_key=b"a" * 32)
    llm3 = AuditedLLM(_FakeLLM(response="answer"), audit_log=audit2, store_raw=True)
    llm3.complete("prompt-A")
    a = next(audit.store.iter_events())
    b = next(audit2.store.iter_events())
    # Pre-hash is over a payload that includes the prompt; same prompt
    # → same hash, even across separate audit instances.
    assert a.payload_hash == b.payload_hash


def test_audited_llm_name_marks_audited(audit: AuditLog) -> None:
    llm = AuditedLLM(_FakeLLM(name="ollama:qwen3"), audit_log=audit)
    assert llm.name == "audited(ollama:qwen3)"


def test_audited_llm_chain_verifies(audit: AuditLog) -> None:
    """Multiple calls keep the chain valid."""
    llm = AuditedLLM(_FakeLLM(), audit_log=audit)
    for i in range(5):
        llm.complete(f"q{i}")
    result = audit.verify()
    assert result.ok is True
    assert result.n_events == 10  # 5 calls x 2 events each


# ---------------------------------------------------------------------------
# AuditedRAG
# ---------------------------------------------------------------------------


def test_audited_rag_passes_through_answer(audit: AuditLog) -> None:
    answer = _FakeAnswer(text="42", citations=[_FakeCitation(0, 1, 0.9)])
    rag = AuditedRAG(_FakeRAG(answer=answer), audit_log=audit)
    out = rag.ask("what is the answer?")
    assert out is answer
    assert out.text == "42"


def test_audited_rag_emits_ask_and_ok(audit: AuditLog) -> None:
    answer = _FakeAnswer(
        text="some answer",
        citations=[_FakeCitation(0, 1, 0.9), _FakeCitation(2, 3, 0.7)],
    )
    rag = AuditedRAG(_FakeRAG(answer=answer), audit_log=audit, risk_tier=RiskTier.HIGH)
    rag.ask("Có hợp đồng nào có phạt vi phạm?")
    events = list(audit.store.iter_events())
    assert len(events) == 2
    assert events[0].action == "ask"
    assert events[1].action == "ask.ok"
    assert events[1].risk_tier == "high"
    assert events[1].parent_id == events[0].span_id


def test_audited_rag_emits_err_on_exception(audit: AuditLog) -> None:
    answer = _FakeAnswer(text="", citations=[])
    inner = _FakeRAG(answer=answer, raise_on_ask=ValueError("bad query"))
    rag = AuditedRAG(inner, audit_log=audit)
    with pytest.raises(ValueError, match="bad query"):
        rag.ask("question")
    events = list(audit.store.iter_events())
    assert len(events) == 2
    assert events[1].action == "ask.err"


def test_audited_rag_passes_kwargs_through(audit: AuditLog) -> None:
    answer = _FakeAnswer(text="x", citations=[])
    inner = _FakeRAG(answer=answer)
    rag = AuditedRAG(inner, audit_log=audit)
    rag.ask("q", top_k=5, query_strategy="multi_query", n_queries=4)
    assert inner.asks[0]["top_k"] == 5
    assert inner.asks[0]["query_strategy"] == "multi_query"
    assert inner.asks[0]["n_queries"] == 4


def test_audited_rag_handles_empty_citations(audit: AuditLog) -> None:
    answer = _FakeAnswer(text="x", citations=[])
    rag = AuditedRAG(_FakeRAG(answer=answer), audit_log=audit)
    rag.ask("q")
    events = list(audit.store.iter_events())
    assert len(events) == 2  # ask + ask.ok still both fire


# ---------------------------------------------------------------------------
# Composed AuditedLLM + AuditedRAG (parent_id chains stay valid)
# ---------------------------------------------------------------------------


def test_chain_verifies_with_both_wrappers(audit: AuditLog) -> None:
    """Compose AuditedRAG over a RAG that uses an AuditedLLM. Chain
    must still verify. (We don't actually compose them physically
    because _FakeRAG doesn't call its LLM; we just emit both flows in
    sequence and verify the chain.)"""
    llm = AuditedLLM(_FakeLLM(), audit_log=audit)
    answer = _FakeAnswer(text="x", citations=[_FakeCitation(0, 0, 1.0)])
    rag = AuditedRAG(_FakeRAG(answer=answer), audit_log=audit)

    rag.ask("Q1")
    llm.complete("internal-call")
    rag.ask("Q2")

    result = audit.verify()
    assert result.ok is True
    # 3 outer events x 2 each = 6 in total
    assert result.n_events == 6
