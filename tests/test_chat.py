"""Tests for nom.chat — FastAPI server + Store.

Uses TestClient so no real ASGI server starts. The LLM and Embedder
are test doubles (deterministic, no model downloads, no network).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

# Skip the whole module if FastAPI isn't installed.
fastapi = pytest.importorskip("fastapi")
testclient_mod = pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient  # noqa: E402

from nom.chat.server import build_app  # noqa: E402
from nom.chat.sqlite_store import SqliteStore  # noqa: E402
from nom.chat.store import MemoryStore, Store  # noqa: E402

# ruff: noqa: I001 — these import as test-doubles below the noqa-E402 block
from tests._fakes import CountingEmbedder as _CountingEmbedder  # noqa: E402
from tests._fakes import FakeEmbedder as _FakeEmbedder  # noqa: E402
from tests._fakes import FakeLLM as _FakeLLM  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    store = MemoryStore(embedder=_FakeEmbedder(), llm=_FakeLLM())
    app = build_app(store=store)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Basic routing + landing page
# ---------------------------------------------------------------------------


class TestRoot:
    def test_root_serves_html(self, client: TestClient) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Nôm" in r.text  # brand mark in chrome

    def test_openapi_docs_available(self, client: TestClient) -> None:
        r = client.get("/docs")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Spaces — CRUD
# ---------------------------------------------------------------------------


class TestSpaces:
    def test_list_initially_empty(self, client: TestClient) -> None:
        r = client.get("/api/spaces")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_then_list(self, client: TestClient) -> None:
        r = client.post("/api/spaces", json={"name": "Contracts 2025"})
        assert r.status_code == 201
        space = r.json()
        assert space["name"] == "Contracts 2025"
        assert space["id"]
        assert space["n_materials"] == 0

        r2 = client.get("/api/spaces")
        names = [s["name"] for s in r2.json()]
        assert "Contracts 2025" in names

    def test_create_empty_name_rejected(self, client: TestClient) -> None:
        r = client.post("/api/spaces", json={"name": "   "})
        assert r.status_code == 400

    def test_get_unknown_404(self, client: TestClient) -> None:
        r = client.get("/api/spaces/bogus")
        assert r.status_code == 404

    def test_delete_known(self, client: TestClient) -> None:
        sid = client.post("/api/spaces", json={"name": "X"}).json()["id"]
        r = client.delete(f"/api/spaces/{sid}")
        assert r.status_code == 204
        assert client.get(f"/api/spaces/{sid}").status_code == 404

    def test_delete_unknown_404(self, client: TestClient) -> None:
        r = client.delete("/api/spaces/bogus")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Materials — upload + list
# ---------------------------------------------------------------------------


class TestMaterials:
    def _space(self, client: TestClient) -> str:
        return client.post("/api/spaces", json={"name": "T"}).json()["id"]

    def test_upload_text_material(self, client: TestClient) -> None:
        sid = self._space(client)
        text = "Hợp đồng số HD-001 ngày 14/3/2025."
        r = client.post(
            f"/api/spaces/{sid}/materials",
            files={"file": ("contract.txt", text.encode("utf-8"), "text/plain")},
        )
        assert r.status_code == 201
        mat = r.json()
        assert mat["name"] == "contract.txt"
        assert mat["n_bytes"] == len(text.encode("utf-8"))

    def test_list_materials(self, client: TestClient) -> None:
        sid = self._space(client)
        client.post(
            f"/api/spaces/{sid}/materials",
            files={"file": ("a.txt", b"hello world", "text/plain")},
        )
        r = client.get(f"/api/spaces/{sid}/materials")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_upload_unknown_space_404(self, client: TestClient) -> None:
        r = client.post(
            "/api/spaces/bogus/materials",
            files={"file": ("x.txt", b"x", "text/plain")},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Ask — end-to-end through the Store
# ---------------------------------------------------------------------------


class TestAsk:
    def _setup(self, client: TestClient) -> str:
        sid = client.post("/api/spaces", json={"name": "Ask test"}).json()["id"]
        client.post(
            f"/api/spaces/{sid}/materials",
            files={
                "file": (
                    "doc.txt",
                    "Hợp đồng số HD-001 ngày 14/3/2025. Tổng giá trị 1.500.000.000 đồng.".encode(),
                    "text/plain",
                )
            },
        )
        return sid

    def test_ask_returns_answer_with_citations(self, client: TestClient) -> None:
        sid = self._setup(client)
        r = client.post(
            f"/api/spaces/{sid}/ask",
            json={"question": "Hợp đồng có giá bao nhiêu?", "top_k": 3},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["text"] == "Mock answer with [1] citation."
        assert len(body["citations"]) > 0
        assert body["n_retrieved"] > 0

    def test_ask_empty_space_returns_empty_answer(self, client: TestClient) -> None:
        sid = client.post("/api/spaces", json={"name": "Empty"}).json()["id"]
        r = client.post(f"/api/spaces/{sid}/ask", json={"question": "anything"})
        assert r.status_code == 200
        body = r.json()
        assert body["citations"] == []
        assert body["n_retrieved"] == 0

    def test_ask_unknown_space_404(self, client: TestClient) -> None:
        r = client.post("/api/spaces/bogus/ask", json={"question": "?"})
        assert r.status_code == 404

    def test_ask_empty_question_rejected(self, client: TestClient) -> None:
        sid = self._setup(client)
        r = client.post(f"/api/spaces/{sid}/ask", json={"question": "   "})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# MemoryStore — directly tested too
# ---------------------------------------------------------------------------


class TestMemoryStore:
    def test_create_and_list(self) -> None:
        s = MemoryStore(embedder=_FakeEmbedder(), llm=_FakeLLM())
        sp = s.create_space("Foo")
        assert sp.name == "Foo"
        assert s.list_spaces()[0].id == sp.id

    def test_empty_name_rejected(self) -> None:
        s = MemoryStore(embedder=_FakeEmbedder(), llm=_FakeLLM())
        with pytest.raises(ValueError, match="empty"):
            s.create_space("   ")

    def test_no_llm_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"llm"):
            MemoryStore(embedder=_FakeEmbedder(), llm=None)  # type: ignore[arg-type]

    def test_add_material_unknown_space(self) -> None:
        s = MemoryStore(embedder=_FakeEmbedder(), llm=_FakeLLM())
        with pytest.raises(KeyError):
            s.add_material("bogus", "x", b"y")


# ---------------------------------------------------------------------------
# Store Protocol conformance — both concrete classes must satisfy it.
# Catches drift if a method is renamed in one impl but not the other.
# ---------------------------------------------------------------------------


class TestStoreProtocol:
    def test_memory_store_conforms(self) -> None:
        s = MemoryStore(embedder=_FakeEmbedder(), llm=_FakeLLM())
        assert isinstance(s, Store)

    def test_sqlite_store_conforms(self, tmp_path: Any) -> None:
        s = SqliteStore(tmp_path, llm=_FakeLLM())
        try:
            assert isinstance(s, Store)
        finally:
            s.close()


# ---------------------------------------------------------------------------
# EmbeddingsCache — the disk cache + the in-memory cache + Protocol
# ---------------------------------------------------------------------------


class TestEmbeddingsCache:
    def test_localdisk_roundtrip(self, tmp_path: Any) -> None:
        from nom.chat.embeddings_cache import EmbeddingsCache, LocalDiskCache

        cache = LocalDiskCache(tmp_path / "vecs")
        assert isinstance(cache, EmbeddingsCache)
        v = np.random.default_rng(0).standard_normal((4, 8), dtype="float32")
        assert not cache.has("a")
        cache.put("a", v)
        assert cache.has("a")
        loaded = cache.get("a")
        assert loaded is not None
        np.testing.assert_array_equal(v, loaded)
        cache.delete("a")
        assert not cache.has("a")
        cache.delete("missing")  # idempotent

    def test_memory_cache_roundtrip(self) -> None:
        from nom.chat.embeddings_cache import EmbeddingsCache, MemoryCache

        cache = MemoryCache()
        assert isinstance(cache, EmbeddingsCache)
        v = np.zeros((2, 3), dtype="float32")
        cache.put("k", v)
        assert cache.get("k") is not None
        # Defensive copy: caller mutations don't poison cache
        v[0, 0] = 99.0
        assert cache.get("k")[0, 0] == 0.0

    def test_sqlite_store_with_injected_memory_cache(self, tmp_path: Any) -> None:
        """Prove the swap: SqliteStore + MemoryCache works end-to-end."""
        from nom.chat.embeddings_cache import MemoryCache

        cache = MemoryCache()
        store = SqliteStore(
            tmp_path,
            llm=_FakeLLM(),
            embedder=_FakeEmbedder(),
            embeddings_cache=cache,
        )
        try:
            sid = store.create_space("S").id
            store.add_material(sid, "a.txt", b"Hop dong so HD-001.")
            ans = store.ask(sid, "?")
            assert ans.text == "Mock answer with [1] citation."
            # Cache was hit during indexing
            mat_id = store.list_materials(sid)[0].id
            assert cache.has(mat_id)
            # Disk was NOT used — no embeddings/ dir under tmp_path
            assert not (tmp_path / "embeddings").is_dir()
        finally:
            store.close()


# ---------------------------------------------------------------------------
# SqliteStore — persistence across reopen
# (test fakes live in tests/_fakes.py and are imported at the top)
# ---------------------------------------------------------------------------


class TestSqliteStore:
    def test_no_llm_rejected(self, tmp_path: Any) -> None:
        with pytest.raises(ValueError, match=r"llm"):
            SqliteStore(tmp_path, llm=None)  # type: ignore[arg-type]

    def test_create_dirs_and_db(self, tmp_path: Any) -> None:
        store = SqliteStore(tmp_path / "data", llm=_FakeLLM())
        assert (tmp_path / "data" / "nom.db").exists()
        assert (tmp_path / "data" / "embeddings").is_dir()
        store.close()

    def test_spaces_persist_across_reopen(self, tmp_path: Any) -> None:
        store = SqliteStore(tmp_path, llm=_FakeLLM())
        sp = store.create_space("Contracts 2026")
        store.close()

        store2 = SqliteStore(tmp_path, llm=_FakeLLM())
        spaces = store2.list_spaces()
        assert len(spaces) == 1
        assert spaces[0].id == sp.id
        assert spaces[0].name == "Contracts 2026"
        store2.close()

    def test_materials_persist_with_chunk_counts(self, tmp_path: Any) -> None:
        emb = _CountingEmbedder()
        store = SqliteStore(tmp_path, llm=_FakeLLM(), embedder=emb)
        sid = store.create_space("S").id
        store.add_material(sid, "doc.txt", b"Hop dong so HD-001 ngay 14/3/2026.")
        # Before ask, indexing hasn't happened — n_chunks is 0
        mats_before = store.list_materials(sid)
        assert mats_before[0].n_chunks == 0
        # Ask triggers indexing (parse → chunk → embed → persist)
        ans = store.ask(sid, "Hop dong gi?")
        assert len(ans.citations) > 0
        mats_after = store.list_materials(sid)
        assert mats_after[0].n_chunks > 0
        store.close()

        # Reopen — chunk counts must survive
        store2 = SqliteStore(tmp_path, llm=_FakeLLM())
        mats_reload = store2.list_materials(sid)
        assert len(mats_reload) == 1
        assert mats_reload[0].n_chunks == mats_after[0].n_chunks
        store2.close()

    def test_reopen_does_not_re_embed_indexed_materials(self, tmp_path: Any) -> None:
        emb1 = _CountingEmbedder()
        store = SqliteStore(tmp_path, llm=_FakeLLM(), embedder=emb1)
        sid = store.create_space("S").id
        text = "Hợp đồng số HD-001 ngày 14/3/2026. Tổng giá trị 1.500.000.000 đồng."
        store.add_material(sid, "doc.txt", text.encode("utf-8"))
        store.ask(sid, "Hỏi gì?")  # triggers embed_batch
        first_batch_calls = emb1.batch_calls
        assert first_batch_calls >= 1
        store.close()

        # Reopen with a NEW embedder — if persistence works, it should
        # never be called for batch (cached embeddings load from disk).
        emb2 = _CountingEmbedder()
        store2 = SqliteStore(tmp_path, llm=_FakeLLM(), embedder=emb2)
        ans = store2.ask(sid, "Hỏi gì?")
        assert ans.text == "Mock answer with [1] citation."
        # Question still needs to be embedded for dense retrieval
        # — that uses embed(), not embed_batch().
        assert emb2.batch_calls == 0, "reopened store should not re-embed indexed materials"
        assert emb2.single_calls >= 1, "question embedding should still happen"
        store2.close()

    def test_delete_space_removes_embedding_files(self, tmp_path: Any) -> None:
        store = SqliteStore(tmp_path, llm=_FakeLLM(), embedder=_CountingEmbedder())
        sid = store.create_space("S").id
        store.add_material(sid, "a.txt", b"Tieng Viet du de phan loai.")
        store.ask(sid, "?")  # trigger indexing
        emb_dir = tmp_path / "embeddings"
        assert any(emb_dir.iterdir()), "expected at least one .npy after indexing"

        assert store.delete_space(sid) is True
        assert store.get_space(sid) is None
        assert not list(emb_dir.iterdir()), "embedding files should be cleaned up on delete"
        store.close()

    def test_ask_empty_space_returns_empty_answer(self, tmp_path: Any) -> None:
        store = SqliteStore(tmp_path, llm=_FakeLLM(), embedder=_CountingEmbedder())
        sid = store.create_space("S").id
        ans = store.ask(sid, "anything")
        assert ans.citations == []
        assert ans.n_retrieved == 0
        store.close()

    def test_works_through_build_app(self, tmp_path: Any) -> None:
        """End-to-end: SqliteStore plugged into the FastAPI server."""
        store = SqliteStore(tmp_path, llm=_FakeLLM(), embedder=_CountingEmbedder())
        client = TestClient(build_app(store=store))
        try:
            sid = client.post("/api/spaces", json={"name": "X"}).json()["id"]
            client.post(
                f"/api/spaces/{sid}/materials",
                files={"file": ("a.txt", "Hợp đồng HD-001.".encode(), "text/plain")},
            )
            r = client.post(f"/api/spaces/{sid}/ask", json={"question": "?"})
            assert r.status_code == 200
            assert r.json()["text"] == "Mock answer with [1] citation."
        finally:
            store.close()
