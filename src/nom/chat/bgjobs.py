"""Lightweight background-job runner for the chat UI.

Distinct from :mod:`nom.jobs` (which is the durable, audit-logged
enterprise queue used for indexing / agent runs). This module is for
**foreground UI flows that need a progress bar**: upload a file, poll
the percentage every 500 ms, click "download" when it finishes.

Why not reuse ``nom.jobs``? That queue is durability-first — SQLite
backing, retry policy, audit trail. Overkill (and the wrong shape)
for "user dropped a 30-page PDF, show a percentage." Two namespaces,
two jobs.

Design:

- One process-wide :class:`JobRunner` (lazy module singleton via
  :func:`get_runner`). State lost on restart — desktop / single-tenant
  is the deployment shape.
- Job functions are sync. ``ThreadPoolExecutor`` keeps them off the
  event loop without forcing every backend (Tesseract, transformers,
  pdfplumber) to be ``async``.
- Progress is callback-driven — the job receives a
  :class:`ProgressReporter` and calls ``update(0.5)`` between units.
  No magic, no decorators.
- Cancellation is cooperative — the job calls
  ``reporter.raise_if_cancelled()`` between units. Hard preemption
  isn't safe with C extensions.
- Result is one file on disk in a per-job temp dir. The HTTP layer
  streams it on download and calls :meth:`JobRunner.cleanup` after.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

__all__ = [
    "BgJob",
    "BgJobCancelledError",
    "BgJobRunner",
    "BgJobStatus",
    "BgJobStore",
    "InMemoryBgJobStore",
    "ProgressReporter",
    "get_runner",
    "reset_runner_for_tests",
]


BgJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class BgJob:
    """A single background-job snapshot.

    Immutable — every state transition replaces the entry in the store
    via :meth:`BgJobStore.update`. UI clients see a consistent snapshot
    per poll.
    """

    id: str
    kind: str
    status: BgJobStatus
    progress: float
    message: str
    created_at: float
    updated_at: float
    result_path: str | None = None
    result_filename: str | None = None
    result_meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BgJobCancelledError(Exception):
    """Raised inside a job function when the caller cancels.

    The runner catches this and transitions to ``cancelled``; other
    exceptions transition to ``failed``.
    """


class ProgressReporter:
    """Thread-safe handle a job uses to report progress.

    Call :meth:`update` to advance the percentage and
    :meth:`raise_if_cancelled` between units to honour cancellation.
    """

    def __init__(self, job_id: str, store: BgJobStore) -> None:
        self._job_id = job_id
        self._store = store
        self._cancelled = False
        self._lock = threading.Lock()

    def update(self, progress: float, *, message: str = "") -> None:
        clamped = 0.0 if progress < 0.0 else (1.0 if progress > 1.0 else float(progress))
        self._store.update(self._job_id, progress=clamped, message=message)

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise BgJobCancelledError()


@runtime_checkable
class BgJobStore(Protocol):
    """Storage seam — default :class:`InMemoryBgJobStore` is fine for
    single-process deployments."""

    def create(self, job: BgJob) -> None: ...
    def get(self, job_id: str) -> BgJob | None: ...
    def list(self) -> list[BgJob]: ...
    def update(
        self,
        job_id: str,
        *,
        status: BgJobStatus | None = None,
        progress: float | None = None,
        message: str | None = None,
        result_path: str | None = None,
        result_filename: str | None = None,
        result_meta: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> BgJob | None: ...
    def delete(self, job_id: str) -> bool: ...


class InMemoryBgJobStore:
    """Thread-safe in-memory :class:`BgJobStore`."""

    def __init__(self) -> None:
        self._jobs: dict[str, BgJob] = {}
        self._lock = threading.Lock()

    def create(self, job: BgJob) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: str) -> BgJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[BgJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def update(
        self,
        job_id: str,
        *,
        status: BgJobStatus | None = None,
        progress: float | None = None,
        message: str | None = None,
        result_path: str | None = None,
        result_filename: str | None = None,
        result_meta: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> BgJob | None:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                return None
            patch: dict[str, Any] = {"updated_at": time.time()}
            if status is not None:
                patch["status"] = status
            if progress is not None:
                patch["progress"] = progress
            if message is not None:
                patch["message"] = message
            if result_path is not None:
                patch["result_path"] = result_path
            if result_filename is not None:
                patch["result_filename"] = result_filename
            if result_meta is not None:
                patch["result_meta"] = result_meta
            if error is not None:
                patch["error"] = error
            updated = replace(current, **patch)
            self._jobs[job_id] = updated
            return updated

    def delete(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None


# Job function signature: receives the per-job temp dir + reporter,
# returns (result_path, result_filename, result_meta).
JobFn = Callable[[Path, ProgressReporter], "tuple[Path, str, dict[str, Any]]"]


class BgJobRunner:
    """Submit job functions to a thread pool; track via a :class:`BgJobStore`."""

    def __init__(
        self,
        store: BgJobStore,
        *,
        max_workers: int = 4,
        root_dir: Path | None = None,
    ) -> None:
        self._store = store
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="nom-bgjob")
        self._reporters: dict[str, ProgressReporter] = {}
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.Lock()
        self._root_dir = root_dir or Path(tempfile.gettempdir()) / "nom-bgjobs"
        self._root_dir.mkdir(parents=True, exist_ok=True)

    @property
    def store(self) -> BgJobStore:
        return self._store

    def submit(self, kind: str, fn: JobFn, *, message: str = "") -> BgJob:
        job_id = uuid.uuid4().hex
        now = time.time()
        job = BgJob(
            id=job_id,
            kind=kind,
            status="queued",
            progress=0.0,
            message=message or "queued",
            created_at=now,
            updated_at=now,
        )
        self._store.create(job)
        reporter = ProgressReporter(job_id, self._store)
        with self._lock:
            self._reporters[job_id] = reporter
        future = self._executor.submit(self._run, job_id, fn, reporter)
        with self._lock:
            self._futures[job_id] = future
        return job

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            reporter = self._reporters.get(job_id)
        if reporter is None:
            return False
        reporter.cancel()
        snap = self._store.get(job_id)
        if snap is not None and snap.status == "queued":
            self._store.update(job_id, status="cancelled", message="cancelled by user")
        return True

    def cleanup(self, job_id: str) -> None:
        """Delete the job's temp dir and drop its reporter / future handle."""
        job_dir = self._root_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        with self._lock:
            self._reporters.pop(job_id, None)
            self._futures.pop(job_id, None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job_id: str, fn: JobFn, reporter: ProgressReporter) -> None:
        snap = self._store.get(job_id)
        if reporter.cancelled or (snap is not None and snap.status == "cancelled"):
            return
        self._store.update(job_id, status="running", message="started")
        job_dir = self._root_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        try:
            result_path, result_filename, meta = fn(job_dir, reporter)
            self._store.update(
                job_id,
                status="completed",
                progress=1.0,
                message="completed",
                result_path=str(result_path),
                result_filename=result_filename,
                result_meta=meta,
            )
        except BgJobCancelledError:
            self._store.update(job_id, status="cancelled", message="cancelled by user")
        except Exception as exc:
            self._store.update(
                job_id,
                status="failed",
                message=f"failed: {type(exc).__name__}",
                error=str(exc) or type(exc).__name__,
            )


# ---------------------------------------------------------------------------
# Process-wide singleton — one runner per server process.

_runner: BgJobRunner | None = None
_runner_lock = threading.Lock()


def get_runner() -> BgJobRunner:
    """Return the process-wide :class:`BgJobRunner`, creating it on demand."""
    global _runner
    with _runner_lock:
        if _runner is None:
            _runner = BgJobRunner(InMemoryBgJobStore())
        return _runner


def reset_runner_for_tests() -> None:
    """Drop the singleton — tests use this for isolation."""
    global _runner
    with _runner_lock:
        if _runner is not None:
            _runner.shutdown()
        _runner = None
