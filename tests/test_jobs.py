"""Tests for ``nom.jobs`` — queue (in-memory + SQLite) + worker.

Concurrency tests use threads. Multi-process semantics are
out of scope here (covered in deployment integration).
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from nom.jobs import (
    InMemoryJobQueue,
    Job,
    JobAttempt,
    JobNotFoundError,
    JobQueue,
    JobResult,
    JobState,
    JobWorker,
    SQLiteJobQueue,
)

# ---------- queue contract (parametrised over impls) ----------------


@pytest.fixture(params=["memory", "sqlite"])
def queue(request: pytest.FixtureRequest, tmp_path: Path) -> JobQueue:
    if request.param == "memory":
        return InMemoryJobQueue()
    return SQLiteJobQueue(db_path=tmp_path / "jobs.sqlite")


def test_enqueue_then_get(queue: JobQueue) -> None:
    job = Job.new(handler_name="noop", payload={"x": 1})
    queue.enqueue(job)
    fetched = queue.get(job.id)
    assert fetched.id == job.id
    assert fetched.payload == {"x": 1}
    assert fetched.state is JobState.QUEUED


def test_get_unknown_raises(queue: JobQueue) -> None:
    with pytest.raises(JobNotFoundError):
        queue.get("nonexistent")


def test_claim_returns_none_when_empty(queue: JobQueue) -> None:
    assert queue.claim() is None


def test_claim_takes_oldest_first(queue: JobQueue) -> None:
    a = Job.new(handler_name="h", payload={})
    time.sleep(0.001)  # ensure different queued_at
    b = Job.new(handler_name="h", payload={})
    queue.enqueue(a)
    queue.enqueue(b)
    first = queue.claim()
    assert first is not None
    assert first.id == a.id
    assert first.state is JobState.RUNNING


def test_claim_skips_unavailable_jobs(queue: JobQueue) -> None:
    """Job scheduled for the future is not returned."""
    future = time.time() + 60
    a = Job.new(handler_name="h", payload={}, scheduled_for=future)
    queue.enqueue(a)
    assert queue.claim() is None


def test_complete_records_attempt(queue: JobQueue) -> None:
    job = Job.new(handler_name="h", payload={})
    queue.enqueue(job)
    queue.claim()
    attempt = JobAttempt(
        started_at=time.time(), finished_at=time.time(), ok=True, output_preview="done"
    )
    completed = queue.complete(job.id, attempt=attempt)
    assert completed.state is JobState.SUCCEEDED
    assert completed.attempts[-1].output_preview == "done"


def test_fail_with_retry_returns_to_queued(queue: JobQueue) -> None:
    job = Job.new(handler_name="h", payload={}, max_attempts=3)
    queue.enqueue(job)
    queue.claim()
    a = JobAttempt(time.time(), time.time(), ok=False, error="boom")
    failed_once = queue.fail(job.id, attempt=a, retry_in_seconds=0.0)
    assert failed_once.state is JobState.QUEUED
    assert failed_once.n_attempts == 1


def test_fail_after_max_attempts_marks_failed(queue: JobQueue) -> None:
    job = Job.new(handler_name="h", payload={}, max_attempts=2)
    queue.enqueue(job)
    # 1st attempt
    queue.claim()
    a1 = JobAttempt(time.time(), time.time(), ok=False, error="first")
    queue.fail(job.id, attempt=a1, retry_in_seconds=0.0)
    # 2nd attempt — failure exhausts max_attempts → FAILED
    queue.claim()
    a2 = JobAttempt(time.time(), time.time(), ok=False, error="second")
    final = queue.fail(job.id, attempt=a2, retry_in_seconds=0.0)
    assert final.state is JobState.FAILED
    assert final.n_attempts == 2


def test_list_filtered_by_state(queue: JobQueue) -> None:
    a = Job.new(handler_name="h", payload={"k": 1})
    b = Job.new(handler_name="h", payload={"k": 2})
    queue.enqueue(a)
    queue.enqueue(b)
    queue.claim()  # one becomes RUNNING

    queued = queue.list(state=JobState.QUEUED)
    running = queue.list(state=JobState.RUNNING)
    assert len(queued) == 1
    assert len(running) == 1


# ---------- worker --------------------------------------------------


@pytest.fixture
def worker_setup(tmp_path: Path) -> dict[str, Any]:
    queue = InMemoryJobQueue()
    log: list[Mapping[str, Any]] = []

    def echo(payload: Mapping[str, Any]) -> JobResult:
        log.append({"payload": dict(payload)})
        return JobResult(output={"ok": True}, output_preview="ok")

    def explode(payload: Mapping[str, Any]) -> JobResult:
        del payload
        raise RuntimeError("intentional")

    worker = JobWorker(
        queue=queue,
        handlers={"echo": echo, "explode": explode},
        backoff_base_seconds=0.0,  # zero backoff for tests
    )
    return {"queue": queue, "worker": worker, "log": log}


def test_worker_runs_one_job(worker_setup: dict[str, Any]) -> None:
    queue = worker_setup["queue"]
    worker = worker_setup["worker"]
    job = Job.new(handler_name="echo", payload={"k": 1})
    queue.enqueue(job)
    out = worker.run_one()
    assert out is not None
    assert out.state is JobState.SUCCEEDED
    assert worker_setup["log"] == [{"payload": {"k": 1}}]


def test_worker_run_one_returns_none_when_empty(worker_setup: dict[str, Any]) -> None:
    assert worker_setup["worker"].run_one() is None


def test_worker_handles_unknown_handler(worker_setup: dict[str, Any]) -> None:
    queue = worker_setup["queue"]
    worker = worker_setup["worker"]
    job = Job.new(handler_name="ghost", payload={})
    queue.enqueue(job)
    out = worker.run_one()
    assert out is not None
    # Unknown handler → fail without retry (max_attempts default 3, but
    # the queue.fail call from worker passes retry_in_seconds=None for
    # unknown-handler path).
    assert out.state is JobState.FAILED
    assert "no handler" in (out.attempts[-1].error or "")


def test_worker_retries_on_handler_exception(worker_setup: dict[str, Any]) -> None:
    queue = worker_setup["queue"]
    worker = worker_setup["worker"]
    job = Job.new(handler_name="explode", payload={}, max_attempts=2)
    queue.enqueue(job)

    # First attempt: fails with retry
    out1 = worker.run_one()
    assert out1 is not None
    assert out1.state is JobState.QUEUED  # requeued for retry
    assert out1.n_attempts == 1

    # Second attempt: max_attempts reached → FAILED
    out2 = worker.run_one()
    assert out2 is not None
    assert out2.state is JobState.FAILED
    assert out2.n_attempts == 2


def test_worker_run_forever_can_be_stopped() -> None:
    """Smoke: start a worker thread, enqueue a job, wait for it,
    then stop. Tests the threaded path without depending on timing."""
    queue = InMemoryJobQueue()
    done = []

    def handler(payload: Mapping[str, Any]) -> JobResult:
        done.append(dict(payload))
        return JobResult()

    worker = JobWorker(
        queue=queue,
        handlers={"h": handler},
        poll_interval_seconds=0.01,
        backoff_base_seconds=0.0,
    )
    worker.start()
    try:
        queue.enqueue(Job.new(handler_name="h", payload={"x": 1}))
        # Wait for completion (bounded).
        for _ in range(200):
            if done:
                break
            time.sleep(0.01)
        assert done == [{"x": 1}]
    finally:
        worker.stop(timeout=2.0)


def test_worker_emits_audit_when_log_provided(tmp_path: Path) -> None:
    """When an AuditLog is wired in, every transition lands in the chain."""
    import secrets

    from nom.compliance.audit import AuditLog

    audit = AuditLog.sqlite(tmp_path / "audit.db", signing_key=secrets.token_bytes(32))
    queue = InMemoryJobQueue()
    worker = JobWorker(
        queue=queue,
        handlers={
            "echo": lambda payload: JobResult(output_preview="ok"),
        },
        audit_log=audit,
        backoff_base_seconds=0.0,
    )
    queue.enqueue(Job.new(handler_name="echo", payload={"k": 1}))
    worker.run_one()

    # Verify chain integrity + the events we expect.
    verified = audit.verify()
    assert verified.ok
    actions = [e.action for e in audit.store.iter_events()]
    assert "job.start" in actions
    assert "job.complete" in actions


# ---------- SQLite queue durability across instances ----------------


def test_sqlite_queue_survives_reopen(tmp_path: Path) -> None:
    db = tmp_path / "jobs.sqlite"
    q1 = SQLiteJobQueue(db_path=db)
    q1.enqueue(Job.new(handler_name="h", payload={"k": 7}))

    # New instance reads the same file.
    q2 = SQLiteJobQueue(db_path=db)
    jobs = q2.list()
    assert len(jobs) == 1
    assert jobs[0].payload == {"k": 7}
