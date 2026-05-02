"""``JobQueue`` Protocol + in-memory and SQLite-backed implementations.

Queues are intentionally simple: ``enqueue``, ``claim`` (atomic
"take next available job, mark running"), ``complete``, ``fail``
(retry-or-give-up). The worker drives the loop.

SQLite uses a tight transaction around the claim so two workers on
the same host don't pick the same job; multi-host deployments need
either Postgres ``SELECT FOR UPDATE SKIP LOCKED`` or Redis primitives
— add a new ``Store`` implementation, no public API change.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from nom.jobs.types import Job, JobAttempt, JobState

__all__ = [
    "InMemoryJobQueue",
    "JobNotFoundError",
    "JobQueue",
    "SQLiteJobQueue",
]


class JobNotFoundError(LookupError):
    """No job matched the requested id."""


@runtime_checkable
class JobQueue(Protocol):
    def enqueue(self, job: Job) -> Job:
        """Persist ``job`` in QUEUED state."""
        ...

    def claim(self) -> Job | None:
        """Atomically pick the oldest available QUEUED job and mark
        it RUNNING. Returns None when no job is ready."""
        ...

    def complete(self, job_id: str, *, attempt: JobAttempt) -> Job:
        """Mark ``job_id`` SUCCEEDED with ``attempt`` appended."""
        ...

    def fail(
        self,
        job_id: str,
        *,
        attempt: JobAttempt,
        retry_in_seconds: float | None = None,
    ) -> Job:
        """Record an attempt failure. When ``retry_in_seconds`` is
        provided AND attempts < max_attempts, the job goes back to
        QUEUED with ``available_at`` bumped; otherwise FAILED."""
        ...

    def get(self, job_id: str) -> Job:
        """Look up by id. Raises :class:`JobNotFoundError`."""
        ...

    def list(self, *, state: JobState | None = None, limit: int = 100) -> list[Job]:
        """Enumerate jobs, optionally filtered by state."""
        ...


@dataclass
class InMemoryJobQueue:
    """Single-process job queue. Useful for Tier-S / tests / CLI tools.

    Threadsafe (one global lock). Not durable across restarts — when
    the process exits, queued and in-flight work is lost. Move to
    :class:`SQLiteJobQueue` (or further) the moment that matters.
    """

    _jobs: dict[str, Job] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def enqueue(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
        return job

    def claim(self) -> Job | None:
        now = time.time()
        with self._lock:
            candidates = [
                j
                for j in self._jobs.values()
                if j.state is JobState.QUEUED and j.available_at <= now
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda j: j.queued_at)
            picked = candidates[0]
            updated = _replace(picked, state=JobState.RUNNING)
            self._jobs[picked.id] = updated
            return updated

    def complete(self, job_id: str, *, attempt: JobAttempt) -> Job:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is None:
                raise JobNotFoundError(job_id)
            updated = _replace(
                existing,
                state=JobState.SUCCEEDED,
                attempts=(*existing.attempts, attempt),
            )
            self._jobs[job_id] = updated
            return updated

    def fail(
        self,
        job_id: str,
        *,
        attempt: JobAttempt,
        retry_in_seconds: float | None = None,
    ) -> Job:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is None:
                raise JobNotFoundError(job_id)
            attempts = (*existing.attempts, attempt)
            if retry_in_seconds is not None and len(attempts) < existing.max_attempts:
                next_available = time.time() + retry_in_seconds
                updated = _replace(
                    existing,
                    state=JobState.QUEUED,
                    available_at=next_available,
                    attempts=attempts,
                )
            else:
                updated = _replace(existing, state=JobState.FAILED, attempts=attempts)
            self._jobs[job_id] = updated
            return updated

    def get(self, job_id: str) -> Job:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is None:
                raise JobNotFoundError(job_id)
            return existing

    def list(self, *, state: JobState | None = None, limit: int = 100) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        if state is not None:
            jobs = [j for j in jobs if j.state is state]
        jobs.sort(key=lambda j: j.queued_at)
        return jobs[:limit]


def _replace(job: Job, **changes: Any) -> Job:
    """Frozen dataclass replace helper."""
    from dataclasses import replace

    return replace(job, **changes)


@dataclass
class SQLiteJobQueue:
    """SQLite-backed durable queue.

    Single-host concurrency only — multiple workers on the same DB
    file is fine; multi-host needs Postgres or Redis.
    """

    db_path: str | Path
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    handler_name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    queued_at REAL NOT NULL,
                    available_at REAL NOT NULL,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    tenant_id TEXT,
                    parent_run_id TEXT,
                    attempts_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS jobs_state_avail
                    ON jobs(state, available_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), isolation_level=None, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def enqueue(self, job: Job) -> Job:
        row = job.to_row()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(id, handler_name, payload_json, state,
                                 queued_at, available_at, max_attempts,
                                 tenant_id, parent_run_id, attempts_json)
                VALUES (:id, :handler_name, :payload_json, :state,
                        :queued_at, :available_at, :max_attempts,
                        :tenant_id, :parent_run_id, :attempts_json)
                """,
                row,
            )
        return job

    def claim(self) -> Job | None:
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE state = ? AND available_at <= ?
                    ORDER BY queued_at ASC LIMIT 1
                    """,
                    (JobState.QUEUED.value, now),
                ).fetchone()
                if row is None:
                    conn.execute("COMMIT")
                    return None
                conn.execute(
                    "UPDATE jobs SET state=? WHERE id=?",
                    (JobState.RUNNING.value, row["id"]),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            updated = dict(row)
            updated["state"] = JobState.RUNNING.value
            return Job.from_row(updated)

    def complete(self, job_id: str, *, attempt: JobAttempt) -> Job:
        return self._record(
            job_id, attempt=attempt, new_state=JobState.SUCCEEDED, available_at=None
        )

    def fail(
        self,
        job_id: str,
        *,
        attempt: JobAttempt,
        retry_in_seconds: float | None = None,
    ) -> Job:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise JobNotFoundError(job_id)
            existing = Job.from_row(dict(row))
        attempts = (*existing.attempts, attempt)
        if retry_in_seconds is not None and len(attempts) < existing.max_attempts:
            new_state = JobState.QUEUED
            available_at: float | None = time.time() + retry_in_seconds
        else:
            new_state = JobState.FAILED
            available_at = None
        return self._record(job_id, attempt=attempt, new_state=new_state, available_at=available_at)

    def _record(
        self,
        job_id: str,
        *,
        attempt: JobAttempt,
        new_state: JobState,
        available_at: float | None,
    ) -> Job:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise JobNotFoundError(job_id)
            existing = Job.from_row(dict(row))
            attempts = (*existing.attempts, attempt)
            updated = _replace(
                existing,
                state=new_state,
                available_at=available_at if available_at is not None else existing.available_at,
                attempts=attempts,
            )
            new_row = updated.to_row()
            conn.execute(
                """
                UPDATE jobs SET state=:state, available_at=:available_at,
                                attempts_json=:attempts_json
                WHERE id=:id
                """,
                new_row,
            )
            return updated

    def get(self, job_id: str) -> Job:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise JobNotFoundError(job_id)
            return Job.from_row(dict(row))

    def list(self, *, state: JobState | None = None, limit: int = 100) -> list[Job]:
        with self._connect() as conn:
            if state is None:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY queued_at ASC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE state=? ORDER BY queued_at ASC LIMIT ?",
                    (state.value, limit),
                ).fetchall()
        return [Job.from_row(dict(r)) for r in rows]
