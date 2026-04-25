"""Tests for nom.retrieve — BM25, Dense, hybrid score fusion."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from nom.retrieve import (
    BM25Retriever,
    DenseRetriever,
    FusionMethod,
    Hit,
    hybrid_score,
)

# ---------------------------------------------------------------------------
# Fixtures — small VN corpus
# ---------------------------------------------------------------------------

CORPUS = [
    "Hợp đồng số HD-001 ngày 14/3/2025. Bên A: Cty Hồng Hà.",
    "Công văn số 02 ban hành ngày 1/4/2025 từ Sở Lao động.",
    "Hợp đồng số HD-002 về dịch vụ công nghệ thông tin tổng giá trị 500 triệu đồng.",
    "Đơn xin nghỉ việc của Bà Hương từ tháng 5 năm 2025.",
    "Tổng giá trị hợp đồng là một tỷ năm trăm triệu đồng chẵn.",
]


# ---------------------------------------------------------------------------
# Hit dataclass
# ---------------------------------------------------------------------------


class TestHit:
    def test_minimal(self) -> None:
        h = Hit(idx=0, score=1.5)
        assert h.idx == 0
        assert h.score == 1.5
        assert h.text is None

    def test_frozen(self) -> None:
        h = Hit(idx=0, score=1.0)
        with pytest.raises((AttributeError, TypeError)):
            h.idx = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------


class TestBM25Retriever:
    def test_fit_then_search_finds_relevant(self) -> None:
        r = BM25Retriever.fit(CORPUS)
        hits = r.search("hợp đồng", top_k=3)
        assert len(hits) >= 1
        # Top hit should be one of the contract docs (idx 0, 2, or 4)
        top_text = (hits[0].text or "").lower()
        assert "hợp đồng" in top_text

    def test_empty_corpus_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"at least one"):
            BM25Retriever.fit([])

    def test_invalid_top_k(self) -> None:
        r = BM25Retriever.fit(CORPUS)
        with pytest.raises(ValueError, match=r"top_k"):
            r.search("query", top_k=0)

    def test_oov_query_returns_no_hits(self) -> None:
        r = BM25Retriever.fit(CORPUS)
        hits = r.search("zzzz xxxx yyyy", top_k=5)
        # Out-of-vocabulary terms produce zero scores; we filter zero-score hits
        assert hits == []

    def test_score_array_length_matches_corpus(self) -> None:
        r = BM25Retriever.fit(CORPUS)
        scores = r.score("hợp đồng")
        assert len(scores) == len(CORPUS)
        # Some doc should have a positive score
        assert (scores > 0).any()

    def test_top_k_bounded(self) -> None:
        r = BM25Retriever.fit(CORPUS)
        hits = r.search("đồng", top_k=100)
        assert len(hits) <= len(CORPUS)

    def test_hits_sorted_by_descending_score(self) -> None:
        r = BM25Retriever.fit(CORPUS)
        hits = r.search("hợp đồng", top_k=3)
        for prev, cur in itertools.pairwise(hits):
            assert prev.score >= cur.score

    def test_name(self) -> None:
        r = BM25Retriever.fit(CORPUS)
        assert r.name == "bm25"


# ---------------------------------------------------------------------------
# Dense
# ---------------------------------------------------------------------------


def _make_random_normalized(n: int, d: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    m = rng.standard_normal((n, d), dtype="float32")
    # L2-normalize rows
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class TestDenseRetriever:
    def test_basic_search(self) -> None:
        emb = _make_random_normalized(20, 16)
        r = DenseRetriever(emb)
        q = emb[5]  # query identical to doc 5
        hits = r.search(q, top_k=3)
        # The exact match should be top
        assert hits[0].idx == 5
        assert hits[0].score == pytest.approx(1.0, abs=1e-5)

    def test_with_documents(self) -> None:
        emb = _make_random_normalized(5, 16)
        docs = [f"doc {i}" for i in range(5)]
        r = DenseRetriever(emb, documents=docs)
        hits = r.search(emb[2], top_k=2)
        assert hits[0].idx == 2
        assert hits[0].text == "doc 2"

    def test_rejects_non_2d_embeddings(self) -> None:
        with pytest.raises(ValueError, match=r"2-D"):
            DenseRetriever(np.zeros((5,)))

    def test_rejects_mismatched_documents(self) -> None:
        emb = _make_random_normalized(5, 16)
        with pytest.raises(ValueError, match=r"length"):
            DenseRetriever(emb, documents=["a", "b"])

    def test_query_dim_mismatch_raises(self) -> None:
        emb = _make_random_normalized(5, 16)
        r = DenseRetriever(emb)
        with pytest.raises(ValueError, match=r"dim"):
            r.search(np.zeros(8, dtype="float32"))

    def test_query_must_be_1d(self) -> None:
        emb = _make_random_normalized(5, 16)
        r = DenseRetriever(emb)
        with pytest.raises(ValueError, match=r"1-D"):
            r.search(np.zeros((1, 16), dtype="float32"))

    def test_n_docs_and_dim(self) -> None:
        emb = _make_random_normalized(7, 12)
        r = DenseRetriever(emb)
        assert r.n_docs == 7
        assert r.dim == 12

    def test_invalid_top_k(self) -> None:
        emb = _make_random_normalized(5, 16)
        r = DenseRetriever(emb)
        with pytest.raises(ValueError, match=r"top_k"):
            r.search(emb[0], top_k=0)


# ---------------------------------------------------------------------------
# Hybrid
# ---------------------------------------------------------------------------


def _hits(*pairs: tuple[int, float]) -> list[Hit]:
    return [Hit(idx=i, score=s) for i, s in pairs]


class TestHybridRRF:
    def test_basic(self) -> None:
        bm25_hits = _hits((0, 5.0), (1, 4.0), (2, 3.0))
        dense_hits = _hits((2, 0.9), (1, 0.8), (3, 0.7))
        fused = hybrid_score([bm25_hits, dense_hits], method="rrf", top_k=4)
        # idx 1 and 2 appear in both, so should outrank 0 and 3
        idxs = [h.idx for h in fused]
        assert set(idxs[:2]) <= {1, 2}

    def test_empty_inputs(self) -> None:
        assert hybrid_score([], method="rrf") == []

    def test_single_retriever_passthrough(self) -> None:
        only = _hits((0, 5.0), (1, 4.0))
        fused = hybrid_score([only], method="rrf", top_k=2)
        assert [h.idx for h in fused] == [0, 1]

    def test_text_payload_preserved_first_seen(self) -> None:
        bm25_hits = [Hit(0, 5.0, text="bm25-doc-0"), Hit(1, 4.0)]
        dense_hits = [Hit(0, 0.9, text="dense-doc-0"), Hit(2, 0.8)]
        fused = hybrid_score([bm25_hits, dense_hits], method="rrf", top_k=3)
        # idx 0 should pick up bm25's text (first to surface it)
        for h in fused:
            if h.idx == 0:
                assert h.text == "bm25-doc-0"

    def test_invalid_top_k(self) -> None:
        with pytest.raises(ValueError, match=r"top_k"):
            hybrid_score([[Hit(0, 1.0)]], top_k=0)

    def test_invalid_rrf_k(self) -> None:
        with pytest.raises(ValueError, match=r"rrf_k"):
            hybrid_score([[Hit(0, 1.0)]], rrf_k=0)


class TestHybridWeighted:
    def test_basic(self) -> None:
        bm25_hits = _hits((0, 5.0), (1, 4.0), (2, 3.0))
        dense_hits = _hits((2, 0.9), (1, 0.8), (3, 0.7))
        fused = hybrid_score(
            [bm25_hits, dense_hits],
            method=FusionMethod.WEIGHTED,
            top_k=4,
            weights=[0.5, 0.5],
        )
        assert len(fused) <= 4
        # Hits sorted descending
        for prev, cur in itertools.pairwise(fused):
            assert prev.score >= cur.score

    def test_requires_weights(self) -> None:
        with pytest.raises(ValueError, match=r"weights"):
            hybrid_score([[Hit(0, 1.0)]], method="weighted")

    def test_weights_length_must_match(self) -> None:
        with pytest.raises(ValueError, match=r"length"):
            hybrid_score(
                [[Hit(0, 1.0)], [Hit(1, 1.0)]],
                method="weighted",
                weights=[1.0],
            )

    def test_weights_sum_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match=r"positive"):
            hybrid_score(
                [[Hit(0, 1.0)]],
                method="weighted",
                weights=[0.0],
            )

    def test_constant_scores_normalize_to_one(self) -> None:
        # All scores equal — min-max normalization should not divide by zero
        constant = _hits((0, 0.5), (1, 0.5), (2, 0.5))
        fused = hybrid_score(
            [constant, constant],
            method="weighted",
            weights=[1.0, 1.0],
            top_k=3,
        )
        # No exception, and we get all three back
        assert {h.idx for h in fused} == {0, 1, 2}


# ---------------------------------------------------------------------------
# Integration: BM25 + Dense fused
# ---------------------------------------------------------------------------


class TestIntegrationBM25PlusDense:
    def test_fused_search_works(self) -> None:
        # Build BM25 over the corpus
        bm25 = BM25Retriever.fit(CORPUS)

        # Build dense over deterministic embeddings (1 unit-vector per doc).
        # Simulate "embed query == embed doc 0" so dense surfaces idx 0 hard.
        d = 32
        emb = np.zeros((len(CORPUS), d), dtype="float32")
        for i in range(len(CORPUS)):
            emb[i, i % d] = 1.0  # one-hot per doc — already L2-normalized
        dense = DenseRetriever(emb, documents=CORPUS)

        bm25_hits = bm25.search("hợp đồng", top_k=5)
        dense_hits = dense.search(emb[0], top_k=5)

        fused = hybrid_score([bm25_hits, dense_hits], method="rrf", top_k=3)
        assert len(fused) >= 1
        # The fused results should be a subset of indices that appeared somewhere
        all_idxs = {h.idx for h in bm25_hits} | {h.idx for h in dense_hits}
        for h in fused:
            assert h.idx in all_idxs
