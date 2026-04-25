"""Tests for nom.embeddings.

The real model loads from HuggingFace and weighs ~440 MB. We don't
download it in CI — sentence-transformers' SentenceTransformer is
mocked end-to-end. The opt-in benchmark in benchmarks/perf/ exercises
the real network path.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from nom.embeddings import Embedder, VietnameseEmbedder

# ---------------------------------------------------------------------------
# Construction is cheap — no disk/network at __init__
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_default_model(self) -> None:
        e = VietnameseEmbedder()
        assert e.model_name == "dangvantuan/vietnamese-embedding"
        assert e.name == "dangvantuan/vietnamese-embedding"
        assert e.device == "cpu"
        # No model loaded yet
        assert e._model is None  # type: ignore[reportPrivateUsage]

    def test_custom_model(self) -> None:
        e = VietnameseEmbedder(
            "paraphrase-multilingual-MiniLM-L12-v2",
            device="cuda",
            cache_folder="/tmp/x",
        )
        assert e.model_name == "paraphrase-multilingual-MiniLM-L12-v2"
        assert e.device == "cuda"
        assert e.cache_folder == "/tmp/x"

    def test_repr_marks_lazy(self) -> None:
        e = VietnameseEmbedder()
        assert "lazy" in repr(e)
        assert "dangvantuan/vietnamese-embedding" in repr(e)


# ---------------------------------------------------------------------------
# Lazy load — first .embed() / .dim triggers SentenceTransformer construction
# ---------------------------------------------------------------------------


def _make_fake_st_module(dim: int = 768) -> MagicMock:
    """Build a fake `sentence_transformers` module exposing SentenceTransformer."""
    fake_model = MagicMock()
    fake_model.get_sentence_embedding_dimension.return_value = dim

    def _encode(text_or_texts: Any, **kwargs: Any) -> np.ndarray:
        if isinstance(text_or_texts, str):
            return np.zeros((dim,), dtype="float32")
        return np.zeros((len(text_or_texts), dim), dtype="float32")

    fake_model.encode.side_effect = _encode

    fake_st_class = MagicMock(return_value=fake_model)
    fake_module = MagicMock()
    fake_module.SentenceTransformer = fake_st_class
    return fake_module


@pytest.fixture
def patched_sentence_transformers(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace `sentence_transformers` import with a fake."""
    import sys

    fake = _make_fake_st_module(dim=768)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    return fake


class TestLazyLoad:
    def test_dim_triggers_load(self, patched_sentence_transformers: MagicMock) -> None:
        e = VietnameseEmbedder()
        assert e._model is None  # type: ignore[reportPrivateUsage]
        d = e.dim
        assert d == 768
        assert e._model is not None  # type: ignore[reportPrivateUsage]

    def test_embed_triggers_load_and_returns_1d(
        self, patched_sentence_transformers: MagicMock
    ) -> None:
        e = VietnameseEmbedder()
        v = e.embed("Hợp đồng số 02")
        assert v.shape == (768,)
        # Encode was called with our text
        fake_model = patched_sentence_transformers.SentenceTransformer.return_value
        args, kwargs = fake_model.encode.call_args
        assert args[0] == "Hợp đồng số 02"
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["convert_to_numpy"] is True

    def test_embed_batch_returns_2d(self, patched_sentence_transformers: MagicMock) -> None:
        e = VietnameseEmbedder()
        m = e.embed_batch(["a", "b", "c"], batch_size=8)
        assert m.shape == (3, 768)
        fake_model = patched_sentence_transformers.SentenceTransformer.return_value
        _, kwargs = fake_model.encode.call_args
        assert kwargs["batch_size"] == 8

    def test_empty_batch_returns_empty_2d_array(
        self, patched_sentence_transformers: MagicMock
    ) -> None:
        e = VietnameseEmbedder()
        m = e.embed_batch([])
        assert m.shape == (0, 768)
        # Encode should NOT have been called for empty input
        fake_model = patched_sentence_transformers.SentenceTransformer.return_value
        # Note: dim access triggers a load but not an encode call
        assert fake_model.encode.call_count == 0

    def test_repeated_calls_load_once(self, patched_sentence_transformers: MagicMock) -> None:
        e = VietnameseEmbedder()
        e.embed("x")
        e.embed("y")
        e.embed_batch(["a", "b"])
        # SentenceTransformer constructor should have been called ONCE
        fake_st_ctor = patched_sentence_transformers.SentenceTransformer
        assert fake_st_ctor.call_count == 1

    def test_repr_marks_loaded_after_use(self, patched_sentence_transformers: MagicMock) -> None:
        e = VietnameseEmbedder()
        e.embed("x")
        assert "loaded" in repr(e)


# ---------------------------------------------------------------------------
# Missing dep — friendly error message with install hint
# ---------------------------------------------------------------------------


class TestMissingDep:
    def test_install_hint_when_sentence_transformers_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import builtins

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "sentence_transformers":
                raise ImportError("simulated missing")
            return original_import(name, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(builtins, "__import__", fake_import)
        e = VietnameseEmbedder()
        with pytest.raises(ImportError, match=r"nom-vn\[embeddings\]"):
            e.embed("Hợp đồng")


# ---------------------------------------------------------------------------
# Protocol conformance — VietnameseEmbedder satisfies Embedder
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_satisfies_embedder_protocol(self, patched_sentence_transformers: MagicMock) -> None:
        # Static-typing check: this assignment would fail mypy if VietnameseEmbedder
        # didn't satisfy the protocol. Runtime: just verify attributes exist after load.
        e: Embedder = VietnameseEmbedder()
        e.embed("x")  # trigger load so dim is populated
        assert isinstance(e.name, str)
        assert isinstance(e.dim, int)
        assert callable(e.embed)
        assert callable(e.embed_batch)
