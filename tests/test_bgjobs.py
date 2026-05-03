"""Unit tests for ``nom.chat.bgjobs`` — the lightweight progress runner.

Covers the contract the API and UI rely on: jobs transition through
queued → running → completed; progress reporter clamps to ``[0, 1]``;
cancellation flips the state and surfaces ``BgJobCancelledError`` to the
job function; failures surface the exception type as ``error``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from nom.chat.bgjobs import (
    BgJobCancelledError,
    BgJobRunner,
    InMemoryBgJobStore,
    ProgressReporter,
)


@pytest.fixture
def runner(tmp_path: Path) -> BgJobRunner:
    r = BgJobRunner(InMemoryBgJobStore(), max_workers=2, root_dir=tmp_path / "jobs")
    yield r
    r.shutdown()


def _wait_for_status(runner: BgJobRunner, job_id: str, status: str, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = runner.store.get(job_id)
        if snap is not None and snap.status == status:
            return
        time.sleep(0.05)
    final = runner.store.get(job_id)
    raise AssertionError(
        f"job {job_id} never reached {status}; final state={final.status if final else 'missing'}"
    )


class TestRunner:
    def test_completed_job_writes_result(self, runner: BgJobRunner) -> None:
        def fn(job_dir: Path, reporter: ProgressReporter) -> tuple[Path, str, dict[str, Any]]:
            out = job_dir / "out.txt"
            out.write_text("hello", encoding="utf-8")
            reporter.update(0.5)
            reporter.update(1.0)
            return out, "out.txt", {"chars": 5}

        job = runner.submit("test-write", fn)
        _wait_for_status(runner, job.id, "completed")
        snap = runner.store.get(job.id)
        assert snap is not None
        assert snap.status == "completed"
        assert snap.progress == 1.0
        assert snap.result_filename == "out.txt"
        assert snap.result_meta == {"chars": 5}
        assert snap.result_path is not None
        assert Path(snap.result_path).read_text() == "hello"

    def test_failed_job_records_exception(self, runner: BgJobRunner) -> None:
        def fn(job_dir: Path, reporter: ProgressReporter) -> tuple[Path, str, dict[str, Any]]:
            raise ValueError("boom")

        job = runner.submit("test-fail", fn)
        _wait_for_status(runner, job.id, "failed")
        snap = runner.store.get(job.id)
        assert snap is not None
        assert snap.error == "boom"
        assert snap.message.startswith("failed:")

    def test_cancellation_surfaces_in_job(self, runner: BgJobRunner) -> None:
        started = []
        cancelled = []

        def fn(job_dir: Path, reporter: ProgressReporter) -> tuple[Path, str, dict[str, Any]]:
            started.append(True)
            for i in range(50):
                reporter.update(i / 50)
                try:
                    reporter.raise_if_cancelled()
                except BgJobCancelledError:
                    cancelled.append(True)
                    raise
                time.sleep(0.05)
            return job_dir / "ok", "ok", {}

        job = runner.submit("test-cancel", fn)
        # Wait for the job to actually start, then cancel.
        deadline = time.time() + 2.0
        while time.time() < deadline and not started:
            time.sleep(0.05)
        assert runner.cancel(job.id) is True
        _wait_for_status(runner, job.id, "cancelled")
        assert cancelled  # the worker raised BgJobCancelledError

    def test_progress_reporter_clamps_to_unit_interval(self) -> None:
        store = InMemoryBgJobStore()
        from nom.chat.bgjobs import BgJob

        store.create(
            BgJob(
                id="j1",
                kind="x",
                status="running",
                progress=0.0,
                message="",
                created_at=time.time(),
                updated_at=time.time(),
            )
        )
        rep = ProgressReporter("j1", store)
        rep.update(-1.0)
        assert store.get("j1").progress == 0.0
        rep.update(2.5)
        assert store.get("j1").progress == 1.0
        rep.update(0.42)
        assert store.get("j1").progress == 0.42

    def test_cleanup_removes_temp_dir(self, runner: BgJobRunner) -> None:
        def fn(job_dir: Path, reporter: ProgressReporter) -> tuple[Path, str, dict[str, Any]]:
            (job_dir / "scratch.txt").write_text("x")
            return job_dir / "scratch.txt", "scratch.txt", {}

        job = runner.submit("test-cleanup", fn)
        _wait_for_status(runner, job.id, "completed")
        snap = runner.store.get(job.id)
        assert snap is not None
        assert snap.result_path is not None
        path = Path(snap.result_path)
        assert path.exists()
        runner.cleanup(job.id)
        assert not path.exists()
