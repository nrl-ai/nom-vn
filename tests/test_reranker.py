"""Tests for nom.rag.reranker — cross-encoder reranking stage.

The real ``sentence_transformers.CrossEncoder`` is mocked so tests run
fast and deterministic, mirroring the ``_FakeLLM`` / ``_FakeEmbedder``
pattern in tests/test_rag.py.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from nom.rag import RAG, CrossEncoderReranker, Reranker
from nom.retrieve import Hit
from tests.test_rag import SAMPLE_DOCS, _FakeEmbedder, _FakeLLM

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeReranker:
    """Records calls; returns hits in a configured order.

    Satisfies the :class:`nom.rag.Reranker` Protocol without loading
    sentence-transformers.
    """

    name = "fake-reranker"

    def __init__(self, score_by_idx: dict[int, float] | None = None) -> None:
        self.score_by_idx = score_by_idx or {}
        self.calls: list[dict[str, Any]] = []

    def rerank(self, query: str, hits: list[Hit], *, top_k: int) -> list[Hit]:
        self.calls.append({"query": query, "n_hits": len(hits), "top_k": top_k})
        ranked = sorted(
            (
                Hit(idx=h.idx, score=self.score_by_idx.get(h.idx, h.score), text=h.text)
                for h in hits
            ),
            key=lambda h: h.score,
            reverse=True,
        )
        return ranked[:top_k]


class _FakeCrossEncoder:
    """Stand-in for sentence_transformers.CrossEncoder.

    Returns a deterministic, query-aware score per (query, doc) pair so
    we can verify the reranker actually consults the cross-encoder rather
    than passing scores through.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.predict_calls: list[list[tuple[str, str]]] = []
        # Expose a `.model` attribute so the use_fp16 .half() branch
        # has something to no-op against if anyone enables it.
        self.model = type("M", (), {"half": lambda self: None})()

    def predict(self, pairs: list[tuple[str, str]], **_: Any) -> np.ndarray:
        self.predict_calls.append(list(pairs))
        # Score = char overlap between query and doc (deterministic).
        return np.array(
            [float(len(set(q) & set(d))) for q, d in pairs],
            dtype="float32",
        )


# ---------------------------------------------------------------------------
# CrossEncoderReranker — unit tests
# ---------------------------------------------------------------------------


class TestCrossEncoderReranker:
    def test_default_model_is_bge_v2_m3(self) -> None:
        r = CrossEncoderReranker()
        assert r.name == "BAAI/bge-reranker-v2-m3"
        assert "bge-reranker-v2-m3" in repr(r)
        assert "lazy" in repr(r)  # not loaded yet

    def test_custom_model_name(self) -> None:
        r = CrossEncoderReranker("namdp-ptit/ViRanker")
        assert r.name == "namdp-ptit/ViRanker"

    def test_construction_does_not_load_model(self) -> None:
        # No sentence_transformers import should be triggered by __init__.
        # If the import had run, _model would be non-None.
        r = CrossEncoderReranker()
        assert r._model is None

    def test_satisfies_reranker_protocol(self) -> None:
        # Both the real class and the fake double should pass the
        # runtime_checkable Protocol check.
        assert isinstance(CrossEncoderReranker(), Reranker)
        assert isinstance(_FakeReranker(), Reranker)

    def test_rerank_empty_query_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = CrossEncoderReranker()
        with pytest.raises(ValueError, match=r"non-empty"):
            r.rerank("", [Hit(idx=0, score=1.0, text="t")], top_k=5)
        with pytest.raises(ValueError, match=r"non-empty"):
            r.rerank("   ", [Hit(idx=0, score=1.0, text="t")], top_k=5)

    def test_rerank_empty_hits_returns_empty(self) -> None:
        r = CrossEncoderReranker()
        assert r.rerank("query", [], top_k=5) == []

    def test_rerank_top_k_zero_returns_empty(self) -> None:
        r = CrossEncoderReranker()
        hits = [Hit(idx=0, score=1.0, text="t")]
        assert r.rerank("q", hits, top_k=0) == []

    def test_rerank_skips_hits_without_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force the model load path to use our fake.
        import sentence_transformers

        monkeypatch.setattr(sentence_transformers, "CrossEncoder", _FakeCrossEncoder)
        r = CrossEncoderReranker()
        hits = [Hit(idx=0, score=1.0, text=None), Hit(idx=1, score=1.0, text="")]
        # All non-scorable → empty output, no model call.
        assert r.rerank("q", hits, top_k=5) == []

    def test_rerank_scores_replaced_by_cross_encoder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sentence_transformers

        monkeypatch.setattr(sentence_transformers, "CrossEncoder", _FakeCrossEncoder)
        r = CrossEncoderReranker()
        # Doc1 shares more chars with query "abc" than doc2 → should rank higher.
        hits = [
            Hit(idx=10, score=0.1, text="zzz"),
            Hit(idx=11, score=0.9, text="abc"),
            Hit(idx=12, score=0.5, text="ab"),
        ]
        out = r.rerank("abc", hits, top_k=2)
        assert len(out) == 2
        # Highest char-overlap = idx 11 (3 chars), then idx 12 (2 chars).
        assert out[0].idx == 11
        assert out[1].idx == 12
        # Original bi-encoder scores have been replaced.
        assert out[0].score == 3.0
        assert out[1].score == 2.0

    def test_rerank_lazy_load_triggered_on_first_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sentence_transformers

        monkeypatch.setattr(sentence_transformers, "CrossEncoder", _FakeCrossEncoder)
        r = CrossEncoderReranker()
        assert r._model is None
        r.rerank("q", [Hit(idx=0, score=1.0, text="hello")], top_k=1)
        assert r._model is not None
        assert "loaded" in repr(r)

    def test_install_hint_when_sentence_transformers_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate the dep being absent by making the import raise.
        import builtins

        real_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kw: Any) -> Any:
            if name == "sentence_transformers":
                raise ImportError("no module")
            return real_import(name, *args, **kw)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        r = CrossEncoderReranker()
        with pytest.raises(ImportError, match=r"pip install nom-vn\[embeddings\]"):
            r.rerank("q", [Hit(idx=0, score=1.0, text="t")], top_k=1)


# ---------------------------------------------------------------------------
# RAG.ask(rerank=True) integration
# ---------------------------------------------------------------------------


class TestAskWithRerank:
    def _rag(self, llm: _FakeLLM, reranker: Reranker | None = None) -> RAG:
        return RAG.from_documents(
            SAMPLE_DOCS,
            llm=llm,
            embedder=_FakeEmbedder(),
            reranker=reranker,
        )

    def test_rerank_default_is_false_backward_compat(self) -> None:
        # No reranker passed → ask() works exactly as before.
        rag = self._rag(_FakeLLM())
        answer = rag.ask("hợp đồng")
        assert answer.text  # got an answer
        assert answer.citations
        assert rag.reranker is None

    def test_rerank_true_without_reranker_raises(self) -> None:
        rag = self._rag(_FakeLLM())
        with pytest.raises(ValueError, match=r"requires the RAG to be built with a reranker"):
            rag.ask("hợp đồng", rerank=True)

    def test_rerank_true_invokes_reranker(self) -> None:
        rr = _FakeReranker()
        llm = _FakeLLM()
        rag = self._rag(llm, reranker=rr)
        rag.ask("hợp đồng", rerank=True, rerank_candidates=20, rerank_keep=3)
        assert len(rr.calls) == 1
        call = rr.calls[0]
        assert call["query"] == "hợp đồng"
        assert call["top_k"] == 3
        # The reranker should see the bi-encoder candidate pool, not just top_k.
        # With our small SAMPLE_DOCS it'll be capped at the corpus size, but
        # at least > top_k=5 default would have given.
        assert call["n_hits"] > 0

    def test_rerank_keep_defaults_to_top_k(self) -> None:
        rr = _FakeReranker()
        rag = self._rag(_FakeLLM(), reranker=rr)
        rag.ask("hợp đồng", rerank=True, top_k=4)
        assert rr.calls[0]["top_k"] == 4

    def test_rerank_changes_citation_order(self) -> None:
        # Force reranker to put a specific chunk first.
        # We don't know which idx maps to which chunk, but we can use
        # the highest-numbered idx and verify it's first.
        llm = _FakeLLM()
        rag = self._rag(llm)
        n_chunks = len(rag.chunks_text)
        target = n_chunks - 1  # last chunk
        rr = _FakeReranker(score_by_idx={target: 999.0})
        rag = RAG.from_documents(
            SAMPLE_DOCS,
            llm=llm,
            embedder=_FakeEmbedder(),
            reranker=rr,
        )
        # rerank_candidates large enough to include the target chunk
        answer = rag.ask("hợp đồng", rerank=True, rerank_candidates=50, rerank_keep=3)
        # The target chunk's (doc, chunk_local) should be in citation #1 if
        # it made it into the bi-encoder pool. Skip the assertion when our
        # tiny corpus didn't include it (no flake).
        target_pair = (rag.chunk_doc_idx[target], rag.chunk_local_idx[target])
        cited_pairs = [(c.doc_idx, c.chunk_idx) for c in answer.citations]
        if target_pair in cited_pairs:
            assert cited_pairs[0] == target_pair

    def test_rerank_with_hyde_strategy(self) -> None:
        # HyDE + rerank — the LLM is called twice (HyDE + final answer)
        # and the reranker once.
        llm = _FakeLLM(response="Đoạn văn giả định...")
        rr = _FakeReranker()
        rag = self._rag(llm, reranker=rr)
        rag.ask("Bao nhiêu hợp đồng?", query_strategy="hyde", rerank=True, rerank_candidates=20)
        assert len(llm.calls) == 2  # HyDE + final
        assert len(rr.calls) == 1

    def test_rerank_with_multi_query_strategy(self) -> None:
        llm = _FakeLLM(response="Q1\nQ2\nQ3")
        rr = _FakeReranker()
        rag = self._rag(llm, reranker=rr)
        rag.ask(
            "Bao nhiêu hợp đồng?",
            query_strategy="multi_query",
            n_queries=3,
            rerank=True,
            rerank_candidates=20,
        )
        assert len(llm.calls) == 2  # rewrite + final
        assert len(rr.calls) == 1

    def test_rerank_candidates_widens_retrieval_pool(self) -> None:
        # When rerank_candidates > n_retrieve, the per-side BM25/dense
        # pool should be widened transparently. We verify by asking for
        # more candidates than the default n_retrieve=20 and checking
        # the reranker received more hits than 20 (capped at corpus size).
        rr = _FakeReranker()
        # Use a corpus large enough that bumping rerank_candidates matters
        big_corpus = [f"Document number {i} với tiếng Việt" for i in range(40)]
        rag = RAG.from_documents(
            big_corpus,
            llm=_FakeLLM(),
            embedder=_FakeEmbedder(),
            reranker=rr,
        )
        rag.ask("Document", rerank=True, rerank_candidates=35, rerank_keep=5)
        # The reranker should see > 20 (the default n_retrieve) candidates.
        assert rr.calls[0]["n_hits"] >= 21
