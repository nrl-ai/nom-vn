"""Tests for nom.rag — the high-level RAG facade.

LLM and Embedder are mocked so tests run fast and deterministic.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from nom.rag import RAG, Answer, Citation

# ---------------------------------------------------------------------------
# Fakes that satisfy the Embedder + LLM Protocols
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    """Deterministic, dependency-free embedder for tests."""

    name = "fake-embedder"
    dim = 32

    def embed(self, text: str) -> np.ndarray:
        # Hash text into a stable 32-dim vector, then L2-normalize.
        h = abs(hash(text)) % (2**32)
        rng = np.random.default_rng(h)
        v = rng.standard_normal(self.dim, dtype="float32")
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def embed_batch(self, texts: list[str], *, batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")
        return np.stack([self.embed(t) for t in texts])


class _FakeLLM:
    """Records calls; returns canned responses."""

    name = "fake-llm"

    def __init__(self, response: str = "Mock answer with [1] citation.") -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        self.calls.append({"prompt": prompt, "schema": schema, "max_tokens": max_tokens})
        return self.response


# ---------------------------------------------------------------------------
# Citation + Answer dataclasses
# ---------------------------------------------------------------------------


class TestCitation:
    def test_minimal(self) -> None:
        c = Citation(doc_idx=0, chunk_idx=2, score=0.85, text="some text")
        assert c.doc_idx == 0
        assert c.chunk_idx == 2

    def test_frozen(self) -> None:
        c = Citation(doc_idx=0, chunk_idx=0, score=1.0, text="x")
        with pytest.raises((AttributeError, TypeError)):
            c.doc_idx = 1  # type: ignore[misc]


class TestAnswer:
    def test_minimal(self) -> None:
        a = Answer(text="hi", citations=[], n_retrieved=0)
        assert a.text == "hi"
        assert a.citations == []

    def test_frozen(self) -> None:
        a = Answer(text="x", citations=[], n_retrieved=0)
        with pytest.raises((AttributeError, TypeError)):
            a.text = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RAG.from_documents — construction validates inputs and indexes everything
# ---------------------------------------------------------------------------


SAMPLE_DOCS = [
    "Hợp đồng số HD-001 ngày 14/3/2025. Bên A: Cty Hồng Hà. Tổng giá trị: 1.500.000.000 đồng.",
    "Công văn số 02 ban hành ngày 1/4/2025 từ Sở Lao động Hà Nội.",
    "Hợp đồng số HD-002 về dịch vụ công nghệ thông tin tổng giá trị 500 triệu đồng.",
]


class TestFromDocuments:
    def test_basic_construction(self) -> None:
        rag = RAG.from_documents(
            SAMPLE_DOCS,
            llm=_FakeLLM(),
            embedder=_FakeEmbedder(),
        )
        # Should have chunked + indexed all 3 docs
        assert len(rag.chunks_text) >= 3
        assert len(rag.chunks_text) == len(rag.chunk_doc_idx) == len(rag.chunk_local_idx)
        # BM25 + Dense indexes built
        assert rag.bm25 is not None
        assert rag.dense is not None
        assert rag.dense.dim == _FakeEmbedder.dim

    def test_empty_sources_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"at least one"):
            RAG.from_documents([], llm=_FakeLLM(), embedder=_FakeEmbedder())

    def test_all_empty_strings_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"no chunks"):
            RAG.from_documents(["", "   ", ""], llm=_FakeLLM(), embedder=_FakeEmbedder())

    def test_chunk_provenance_tracked(self) -> None:
        rag = RAG.from_documents(
            SAMPLE_DOCS,
            llm=_FakeLLM(),
            embedder=_FakeEmbedder(),
        )
        # Every chunk should map to a valid source doc index
        for di in rag.chunk_doc_idx:
            assert 0 <= di < len(SAMPLE_DOCS)
        # Local indexes should restart per doc
        seen_pairs: set[tuple[int, int]] = set()
        for di, ci in zip(rag.chunk_doc_idx, rag.chunk_local_idx, strict=True):
            assert (di, ci) not in seen_pairs
            seen_pairs.add((di, ci))


# ---------------------------------------------------------------------------
# ask() — happy path + edge cases
# ---------------------------------------------------------------------------


class TestAsk:
    def _rag(self, llm: _FakeLLM | None = None) -> RAG:
        return RAG.from_documents(
            SAMPLE_DOCS,
            llm=llm or _FakeLLM(),
            embedder=_FakeEmbedder(),
        )

    def test_returns_answer_with_citations(self) -> None:
        llm = _FakeLLM(response="Có 2 hợp đồng [1][2].")
        rag = self._rag(llm)
        answer = rag.ask("Bao nhiêu hợp đồng?")
        assert answer.text == "Có 2 hợp đồng [1][2]."
        assert len(answer.citations) > 0
        assert answer.n_retrieved > 0

    def test_each_citation_has_doc_and_chunk_indexes(self) -> None:
        rag = self._rag()
        answer = rag.ask("hợp đồng")
        for c in answer.citations:
            assert 0 <= c.doc_idx < len(SAMPLE_DOCS)
            assert c.chunk_idx >= 0
            assert c.text  # non-empty

    def test_top_k_override(self) -> None:
        rag = self._rag()
        a3 = rag.ask("hợp đồng", top_k=3)
        a1 = rag.ask("hợp đồng", top_k=1)
        assert len(a3.citations) <= 3
        assert len(a1.citations) <= 1

    def test_empty_question_rejected(self) -> None:
        rag = self._rag()
        with pytest.raises(ValueError, match=r"non-empty"):
            rag.ask("")
        with pytest.raises(ValueError, match=r"non-empty"):
            rag.ask("   ")

    def test_llm_receives_grounded_prompt(self) -> None:
        llm = _FakeLLM()
        rag = self._rag(llm)
        rag.ask("Bao nhiêu hợp đồng?")
        prompt = llm.calls[0]["prompt"]
        assert "Bao nhiêu hợp đồng?" in prompt
        assert "Context" in prompt
        assert "[1]" in prompt or "[ 1 ]" in prompt  # at least one block

    def test_unknown_strategy_rejected(self) -> None:
        rag = self._rag()
        with pytest.raises(ValueError, match=r"Unknown query_strategy"):
            rag.ask("hợp đồng", query_strategy="bogus")


class TestQueryStrategies:
    """HyDE + multi-query — verify the LLM is consulted before retrieval
    and the original question still drives the final answer prompt."""

    def _rag(self, llm: _FakeLLM) -> RAG:
        return RAG.from_documents(
            SAMPLE_DOCS,
            llm=llm,
            embedder=_FakeEmbedder(),
        )

    def test_hyde_makes_two_llm_calls_first_is_query_expansion(self) -> None:
        # First call: hypothetical-answer generation. Second call: final
        # grounded answer. The query-expansion call's prompt must contain
        # the user's question; the final call's prompt must too.
        llm = _FakeLLM(response="Hà Nội là thủ đô…")
        rag = self._rag(llm)
        rag.ask("Thủ đô của Việt Nam là gì?", query_strategy="hyde")
        assert len(llm.calls) == 2
        assert "Thủ đô của Việt Nam là gì?" in llm.calls[0]["prompt"]
        assert "Đoạn văn:" in llm.calls[0]["prompt"]  # HyDE prompt marker
        # Final answer call still sees the original question as-asked
        assert "Thủ đô của Việt Nam là gì?" in llm.calls[1]["prompt"]
        assert "Context" in llm.calls[1]["prompt"]

    def test_multi_query_makes_two_calls_then_retrieves_per_rewrite(self) -> None:
        # The rewrite call returns three lines → 4 total queries
        # (original + 3 rewrites). Final answer is one more LLM call.
        llm = _FakeLLM(response="Q1\nQ2\nQ3")
        rag = self._rag(llm)
        rag.ask("Bao nhiêu hợp đồng?", query_strategy="multi_query", n_queries=3)
        assert len(llm.calls) == 2
        # The final call uses the user's original question
        final_prompt = llm.calls[1]["prompt"]
        assert "Bao nhiêu hợp đồng?" in final_prompt

    def test_direct_strategy_makes_only_one_llm_call(self) -> None:
        # Default behavior unchanged: just the final grounded-answer call.
        llm = _FakeLLM()
        rag = self._rag(llm)
        rag.ask("hợp đồng")
        assert len(llm.calls) == 1


class TestQueryHelpers:
    """The ``hyde`` and ``multi_query`` helpers are also usable
    standalone (e.g., when wiring nom-vn into another framework)."""

    def test_hyde_strips_and_passes_question(self) -> None:
        from nom.rag import hyde

        llm = _FakeLLM(response="  Hà Nội là thủ đô…  \n")
        result = hyde("Thủ đô?", llm)
        assert result == "Hà Nội là thủ đô…"
        assert "Thủ đô?" in llm.calls[0]["prompt"]

    def test_hyde_rejects_empty(self) -> None:
        from nom.rag import hyde

        with pytest.raises(ValueError, match=r"non-empty"):
            hyde("   ", _FakeLLM())

    def test_multi_query_returns_original_plus_n_rewrites(self) -> None:
        from nom.rag import multi_query

        llm = _FakeLLM(response="Rewrite A\nRewrite B\nRewrite C")
        out = multi_query("Question?", llm, n=3)
        assert out == ["Question?", "Rewrite A", "Rewrite B", "Rewrite C"]

    def test_multi_query_truncates_excess_rewrites(self) -> None:
        from nom.rag import multi_query

        llm = _FakeLLM(response="A\nB\nC\nD\nE")  # LLM emitted 5
        out = multi_query("Q?", llm, n=2)
        assert out == ["Q?", "A", "B"]

    def test_multi_query_rejects_n_zero(self) -> None:
        from nom.rag import multi_query

        with pytest.raises(ValueError, match=r"n="):
            multi_query("Q?", _FakeLLM(), n=0)

    def test_multi_query_drops_blank_lines(self) -> None:
        from nom.rag import multi_query

        llm = _FakeLLM(response="\n\nRewrite A\n  \n\nRewrite B\n")
        out = multi_query("Q?", llm, n=3)
        assert out == ["Q?", "Rewrite A", "Rewrite B"]


# ---------------------------------------------------------------------------
# String-vs-path source detection
# ---------------------------------------------------------------------------


class TestSourceDetection:
    def test_long_strings_treated_as_text(self) -> None:
        # Long string with newlines clearly isn't a path
        long_text = "Hợp đồng số 02. " + "Bên A. " * 20
        rag = RAG.from_documents(
            [long_text],
            llm=_FakeLLM(),
            embedder=_FakeEmbedder(),
        )
        # Construction should succeed without trying to open it as a file
        assert len(rag.chunks_text) >= 1
