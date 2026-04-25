"""Multi-space integration tests — cross-space isolation, scaling sanity.

Drives ``MemoryStore`` and ``SqliteStore`` through realistic scenarios
with several spaces, varying file types, and concurrent operations to
confirm that:

- Materials in one space don't leak into another's RAG.
- Deleting one space doesn't disturb its siblings (cache, embeddings,
  chunks all scoped correctly).
- Indexing one space doesn't trigger work in others.
- Asks return citations only from the asked-on space.
- The same question against two spaces hits the right corpus each time.
- Concurrent ``ask`` calls on different spaces don't deadlock.

Uses the ``_FakeEmbedder`` / ``_FakeLLM`` doubles from ``test_chat.py``
where appropriate (cheap + deterministic).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from nom.chat.sqlite_store import SqliteStore
from nom.chat.store import MemoryStore, Store

# ---------------------------------------------------------------------------
# Fakes — duplicated from test_chat to avoid cross-file fixture coupling.
# ---------------------------------------------------------------------------


class _FakeLLM:
    name = "fake-llm"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(
        self,
        prompt: str,
        *,
        schema: Any | None = None,
        max_tokens: int = 2048,
    ) -> str:
        del schema, max_tokens
        self.calls.append(prompt)
        return "Mock answer with [1] citation."


class _FakeEmbedder:
    name = "fake-embedder"
    dim = 16

    def embed(self, text: str) -> np.ndarray:
        h = abs(hash(text)) % (2**32)
        rng = np.random.default_rng(h)
        v = rng.standard_normal(self.dim, dtype="float32")
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def embed_batch(self, texts: list[str], *, batch_size: int = 32) -> np.ndarray:
        del batch_size
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")
        return np.stack([self.embed(t) for t in texts])


# ---------------------------------------------------------------------------
# Test corpora — different content per space so we can verify isolation.
# ---------------------------------------------------------------------------


SPACES_FIXTURE = {
    "Pháp luật": [
        (
            "luat_dn_2020.txt",
            "Luật Doanh nghiệp 2020 quy định về thành lập, tổ chức quản lý, hoạt động.",
        ),
        (
            "bldsanh_2015.txt",
            "Bộ luật Dân sự 2015 quy định địa vị pháp lý của người, tài sản, hợp đồng.",
        ),
    ],
    "Văn học": [
        ("kieu_001.txt", "Trăm năm trong cõi người ta. Chữ tài chữ mệnh khéo là ghét nhau."),
        (
            "chinh_phu_ngam.txt",
            "Thuở trời đất nổi cơn gió bụi. Khách má hồng nhiều nỗi truân chuyên.",
        ),
    ],
    "Bách khoa": [
        ("vn.txt", "Việt Nam là một quốc gia ở Đông Nam Á. Diện tích khoảng 331,212 km²."),
        ("hanoi.txt", "Hà Nội là thủ đô của Việt Nam. Dân số khoảng 8 triệu người."),
    ],
}


def _seed_three_spaces(store: Store) -> dict[str, str]:
    """Create the 3 fixture spaces, upload their materials. Return name → id."""
    space_ids: dict[str, str] = {}
    for name, materials in SPACES_FIXTURE.items():
        sp = store.create_space(name)
        space_ids[name] = sp.id
        for fname, text in materials:
            store.add_material(sp.id, fname, text.encode("utf-8"))
    return space_ids


# ---------------------------------------------------------------------------
# Parameterized: every test runs against both store implementations.
# ---------------------------------------------------------------------------


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Store:
    if request.param == "memory":
        s: Store = MemoryStore(embedder=_FakeEmbedder(), llm=_FakeLLM())
        yield s
    else:
        s = SqliteStore(tmp_path / "data", llm=_FakeLLM(), embedder=_FakeEmbedder())
        try:
            yield s
        finally:
            s.close()


# ---------------------------------------------------------------------------
# Cross-space isolation — the core invariant.
# ---------------------------------------------------------------------------


class TestSpaceIsolation:
    def test_three_spaces_each_have_only_their_materials(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        for name, sid in ids.items():
            mats = store.list_materials(sid)
            expected = {f for f, _ in SPACES_FIXTURE[name]}
            actual = {m.name for m in mats}
            assert actual == expected, f"{name}: expected {expected}, got {actual} — possible leak"

    def test_list_spaces_returns_all(self, store: Store) -> None:
        _seed_three_spaces(store)
        spaces = store.list_spaces()
        assert len(spaces) == 3
        names = {s.name for s in spaces}
        assert names == set(SPACES_FIXTURE.keys())

    def test_delete_one_space_others_intact(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        # Pre-build all RAGs so we exercise cache invalidation too.
        for sid in ids.values():
            store.ask(sid, "tóm tắt", top_k=1)
        # Delete one space.
        assert store.delete_space(ids["Văn học"]) is True
        # Other two still have their materials.
        assert {m.name for m in store.list_materials(ids["Pháp luật"])} == {
            "luat_dn_2020.txt",
            "bldsanh_2015.txt",
        }
        assert {m.name for m in store.list_materials(ids["Bách khoa"])} == {
            "vn.txt",
            "hanoi.txt",
        }
        # Deleted space gone from list_spaces too.
        assert {s.name for s in store.list_spaces()} == {"Pháp luật", "Bách khoa"}

    def test_get_space_unknown_returns_none(self, store: Store) -> None:
        _seed_three_spaces(store)
        assert store.get_space("definitely-not-an-id") is None

    def test_ask_unknown_space_raises_keyerror(self, store: Store) -> None:
        _seed_three_spaces(store)
        with pytest.raises(KeyError):
            store.ask("bogus", "?")

    def test_get_material_content_scoped_to_space(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        plt_mat = store.list_materials(ids["Pháp luật"])[0]
        # Asking for that material against a DIFFERENT space's id must miss.
        assert (
            store.get_material_content(ids["Văn học"], plt_mat.id) is None
        ), "material id leaked across spaces"
        assert store.get_material_content(ids["Pháp luật"], plt_mat.id) is not None


# ---------------------------------------------------------------------------
# Ask-time isolation — citations only from the asked space's corpus.
# ---------------------------------------------------------------------------


class TestAskIsolation:
    def test_citations_only_from_asked_space(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        # Ask in Văn học — citations must reference Văn học's chunks only.
        ans = store.ask(ids["Văn học"], "Tài mệnh là gì?", top_k=3)
        assert ans.citations
        van_hoc_words = {"Trăm", "Thuở", "khách", "tài", "mệnh", "trời"}
        # At least one citation should mention something from Văn học's corpus.
        text_blob = " ".join(c.text for c in ans.citations)
        assert any(
            w in text_blob for w in van_hoc_words
        ), f"Văn học ask returned citations not from Văn học: {text_blob[:200]}"
        # And NOT mention things from Pháp luật / Bách khoa corpora.
        forbidden = ["Doanh nghiệp 2020", "Hà Nội", "Việt Nam là một"]
        for f in forbidden:
            assert f not in text_blob, f"Văn học citations leaked content from another space: {f!r}"

    def test_same_question_two_spaces_two_corpora(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        ans_a = store.ask(ids["Pháp luật"], "tóm tắt", top_k=2)
        ans_b = store.ask(ids["Bách khoa"], "tóm tắt", top_k=2)
        a_text = " ".join(c.text for c in ans_a.citations)
        b_text = " ".join(c.text for c in ans_b.citations)
        assert "Luật" in a_text or "Bộ luật" in a_text
        assert "Việt Nam" in b_text or "Hà Nội" in b_text
        # Cross-check: no overlap in cited content.
        assert "Luật Doanh nghiệp" not in b_text
        assert "Hà Nội" not in a_text

    def test_empty_space_returns_empty_answer(self, store: Store) -> None:
        sp = store.create_space("Empty space")
        ans = store.ask(sp.id, "anything")
        assert ans.citations == []
        assert ans.n_retrieved == 0


# ---------------------------------------------------------------------------
# Indexing isolation — index_pending only touches the named space.
# ---------------------------------------------------------------------------


class TestIndexingIsolation:
    def test_index_one_space_does_not_index_others(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        assert store.index_pending(ids["Văn học"]) == 2
        # Other spaces still pending.
        for other in ("Pháp luật", "Bách khoa"):
            mats = store.list_materials(ids[other])
            assert all(
                m.n_chunks == 0 for m in mats
            ), f"indexing Văn học triggered indexing in {other}"

    def test_index_pending_idempotent(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        first = store.index_pending(ids["Bách khoa"])
        assert first == 2
        # Second call should index nothing — already done.
        second = store.index_pending(ids["Bách khoa"])
        assert second == 0

    def test_add_material_marks_space_stale(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        store.index_pending(ids["Bách khoa"])
        # Adding a new material to Bách khoa should make it pending again.
        store.add_material(ids["Bách khoa"], "extra.txt", "Đà Nẵng là thành phố biển.".encode())
        assert store.index_pending(ids["Bách khoa"]) == 1


# ---------------------------------------------------------------------------
# Concurrency — multiple spaces being queried at once.
# ---------------------------------------------------------------------------


class TestMultiSpaceConcurrency:
    def test_concurrent_asks_on_different_spaces(self, store: Store) -> None:
        ids = _seed_three_spaces(store)
        targets = list(ids.values()) * 3  # 9 calls
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(store.ask, sid, "tóm tắt", top_k=1) for sid in targets]
            results = [f.result(timeout=15) for f in as_completed(futs)]
        assert len(results) == 9
        for r in results:
            assert r.text  # all answered (Mock answer)

    def test_concurrent_create_then_ask(self, store: Store) -> None:
        """Race-style: create + populate + ask all interleaved across threads."""

        def worker(i: int) -> str:
            sp = store.create_space(f"S{i}")
            store.add_material(sp.id, "x.txt", f"Nội dung {i} cho space {i}.".encode())
            ans = store.ask(sp.id, "?", top_k=1)
            return ans.text

        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = [pool.submit(worker, i) for i in range(6)]
            results = [f.result(timeout=20) for f in as_completed(futs)]
        assert len(results) == 6
        # Six new spaces created; sanity check none collided on id.
        spaces = store.list_spaces()
        assert len({s.id for s in spaces}) == len(spaces)
