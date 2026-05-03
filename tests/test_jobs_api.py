"""Integration tests for ``/api/jobs/*``.

Round-trips the public surface the React UI consumes: enqueue a
translate job, poll until it completes, download the result, delete.
Also locks the polling-friendly contract (POST returns 202 + snapshot,
GET 404 for missing).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient  # noqa: E402

from nom.chat.bgjobs import reset_runner_for_tests  # noqa: E402
from nom.chat.server import build_app  # noqa: E402
from nom.chat.store import MemoryStore  # noqa: E402
from tests._fakes import FakeEmbedder, FakeLLM  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_runner() -> None:
    """Each test gets a fresh module-level BgJobRunner so jobs from one
    test don't leak into another."""
    reset_runner_for_tests()
    yield
    reset_runner_for_tests()


@pytest.fixture
def client() -> TestClient:
    store = MemoryStore(
        embedder=FakeEmbedder(),
        # FakeLLM echoes input wrapped in a pretend translation.
        llm=FakeLLM(response="(translated)"),
    )
    return TestClient(build_app(store=store))


def _wait_until_done(client: TestClient, job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        snap = r.json()
        if snap["status"] in ("completed", "failed", "cancelled"):
            return snap
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished; last={snap}")


class TestListAndGet:
    def test_empty_list(self, client: TestClient) -> None:
        r = client.get("/api/jobs")
        assert r.status_code == 200
        assert r.json() == {"jobs": []}

    def test_get_missing_404(self, client: TestClient) -> None:
        r = client.get("/api/jobs/no-such")
        assert r.status_code == 404


class TestTranslateJob:
    def test_enqueue_and_complete_text_file(self, client: TestClient, tmp_path: Path) -> None:
        src = tmp_path / "hello.txt"
        src.write_text("Hello world.\n\nThis is a test.", encoding="utf-8")

        with src.open("rb") as fh:
            r = client.post(
                "/api/jobs/translate-file",
                files={"file": ("hello.txt", fh, "text/plain")},
                data={"source": "en", "target": "vi", "backend": "llm"},
            )
        assert r.status_code == 202, r.text
        snap = r.json()
        assert snap["kind"] == "translate-file"
        assert snap["status"] == "queued"
        job_id = snap["id"]

        final = _wait_until_done(client, job_id)
        assert final["status"] == "completed", final
        assert final["progress"] == 1.0
        assert final["result_filename"] == "hello.vi.txt"
        assert final["download_url"] == f"/api/jobs/{job_id}/download"
        meta = final["result_meta"]
        assert meta["source"] == "en"
        assert meta["target"] == "vi"
        assert meta["backend"] == "llm"
        assert meta["units_translated"] >= 1

        # Download
        r = client.get(final["download_url"])
        assert r.status_code == 200
        assert b"(translated)" in r.content

    def test_unsupported_format_returns_422(self, client: TestClient, tmp_path: Path) -> None:
        src = tmp_path / "evil.exe"
        src.write_bytes(b"binary")
        with src.open("rb") as fh:
            r = client.post(
                "/api/jobs/translate-file",
                files={"file": ("evil.exe", fh, "application/octet-stream")},
                data={"source": "en", "target": "vi"},
            )
        assert r.status_code == 422

    def test_same_source_target_returns_422(self, client: TestClient, tmp_path: Path) -> None:
        src = tmp_path / "x.txt"
        src.write_text("hi")
        with src.open("rb") as fh:
            r = client.post(
                "/api/jobs/translate-file",
                files={"file": ("x.txt", fh, "text/plain")},
                data={"source": "vi", "target": "vi"},
            )
        assert r.status_code == 422


class TestLifecycle:
    def test_delete_drops_job(self, client: TestClient, tmp_path: Path) -> None:
        src = tmp_path / "x.txt"
        src.write_text("hi")
        with src.open("rb") as fh:
            r = client.post(
                "/api/jobs/translate-file",
                files={"file": ("x.txt", fh, "text/plain")},
                data={"source": "en", "target": "vi"},
            )
        job_id = r.json()["id"]
        _wait_until_done(client, job_id)

        # Delete returns 204 then GET returns 404.
        r = client.delete(f"/api/jobs/{job_id}")
        assert r.status_code == 204
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 404

    def test_download_404_when_not_completed(self, client: TestClient) -> None:
        # No such job at all → 404
        r = client.get("/api/jobs/no-such/download")
        assert r.status_code == 404

    def test_cancel_missing_returns_404(self, client: TestClient) -> None:
        r = client.post("/api/jobs/no-such/cancel")
        assert r.status_code == 404
