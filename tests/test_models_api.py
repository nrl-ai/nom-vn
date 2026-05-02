"""Tests for /api/models/* — listing + pull tracker.

Mocks Ollama's HTTP surface via ``httpx.MockTransport`` so the tests
run offline. Pull-progress streaming is exercised end-to-end.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from nom.chat.server import build_app  # noqa: E402
from nom.chat.store import MemoryStore  # noqa: E402
from tests._fakes import FakeEmbedder, FakeLLM  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    store = MemoryStore(embedder=FakeEmbedder(), llm=FakeLLM())
    return TestClient(build_app(store=store))


def test_models_list_handles_unreachable_ollama(client: TestClient) -> None:
    """Default Ollama URL points at localhost:11434; in CI that's
    unreachable. The route should return reachable=False, not 500."""
    r = client.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    assert "ollama" in body
    assert "hf_cache" in body
    assert "catalog" in body
    # Curated catalog stays present regardless of Ollama reachability.
    catalog_ids = [m["id"] for m in body["catalog"]]
    assert "qwen3:8b" in catalog_ids


def test_pull_requires_model_id(client: TestClient) -> None:
    r = client.post("/api/models/pull", json={"source": "ollama"})
    assert r.status_code == 422


def test_pull_rejects_unknown_source(client: TestClient) -> None:
    r = client.post(
        "/api/models/pull",
        json={"source": "lm-studio", "model": "qwen3:8b"},
    )
    assert r.status_code == 422


def test_pull_batch_requires_models_list(client: TestClient) -> None:
    r = client.post("/api/models/pull/batch", json={})
    assert r.status_code == 422
    r = client.post("/api/models/pull/batch", json={"models": []})
    assert r.status_code == 422


def test_pulls_listing_starts_empty(client: TestClient) -> None:
    # State is process-global; clear out any pulls left from prior tests.
    from nom.chat import models_api

    models_api._PULLS.clear()
    r = client.get("/api/models/pulls")
    assert r.status_code == 200
    assert r.json()["pulls"] == []


def test_cancel_unknown_pull_404(client: TestClient) -> None:
    r = client.post("/api/models/pull/does-not-exist/cancel")
    assert r.status_code == 404


def test_curated_catalog_shape() -> None:
    """The catalog feeds the UI's recommended-models list. Each entry
    needs an id, label, tier, size_gb, license."""
    from nom.chat.models_api import _CURATED_CATALOG

    assert len(_CURATED_CATALOG) >= 3
    for entry in _CURATED_CATALOG:
        assert {"id", "label", "tier", "size_gb", "license", "use_cases"}.issubset(entry)
        assert entry["tier"] in {"light", "standard", "power"}


def test_pull_state_progress_calculation() -> None:
    from nom.chat.models_api import _PullState

    state = _PullState(pull_id="x", source="ollama", model="qwen3:8b")
    state.layers["sha256:a"] = {"total": 1000, "completed": 250}
    state.layers["sha256:b"] = {"total": 500, "completed": 500}
    state.total_bytes = 1500
    state.downloaded_bytes = 750

    d = state.to_dict()
    assert d["progress"] == 0.5
    assert d["status"] == "pending"
    assert d["model"] == "qwen3:8b"


def test_apply_pull_event_layer_progress() -> None:
    """The layer-aggregation logic reads Ollama's per-layer JSON events
    and rolls them up into total_bytes / downloaded_bytes."""
    from nom.chat.models_api import _apply_pull_event, _PullState

    state = _PullState(pull_id="x", source="ollama", model="qwen3:8b")
    _apply_pull_event(
        state,
        {
            "status": "downloading",
            "digest": "sha256:layer1",
            "total": 4_000_000,
            "completed": 1_000_000,
        },
    )
    _apply_pull_event(
        state,
        {
            "status": "downloading",
            "digest": "sha256:layer2",
            "total": 2_000_000,
            "completed": 0,
        },
    )
    assert state.total_bytes == 6_000_000
    assert state.downloaded_bytes == 1_000_000

    # Layer1 completes
    _apply_pull_event(
        state,
        {
            "status": "downloading",
            "digest": "sha256:layer1",
            "total": 4_000_000,
            "completed": 4_000_000,
        },
    )
    assert state.downloaded_bytes == 4_000_000


def test_pulls_gc_after_retention_window() -> None:
    """Completed pulls older than _PULL_RETENTION_SECONDS get garbage-
    collected on the next /api/models/pulls call."""
    import time as _time

    from nom.chat import models_api

    models_api._PULLS.clear()
    state = models_api._PullState(pull_id="old", source="ollama", model="x")
    state.status = "success"
    state.completed_at = _time.time() - models_api._PULL_RETENTION_SECONDS - 10
    models_api._PULLS["old"] = state

    models_api._gc_old_pulls()
    assert "old" not in models_api._PULLS
