"""``JobWorker`` — drain the queue, dispatch jobs, record attempts.

Single-threaded by design. To scale, run N worker processes (or N
threads each with its own ``JobWorker``); the SQLite queue's
atomic claim handles contention. Multi-process on the same DB is
fine; multi-host needs a Postgres / Redis store.

Audit: each lifecycle transition (claim, complete, fail, retry)
emits an event into the optional ``AuditLog`` so a regulator can
replay job execution as part of the chain. Job payloads are hashed
(not stored verbatim) by default — same privacy posture as the LLM
audit wrapper.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nom.jobs.queue import JobNotFoundError, JobQueue
from nom.jobs.types import Job, JobAttempt, JobHandler, JobResult

if TYPE_CHECKING:
    from nom.compliance.audit.log import AuditLog

__all__ = ["JobWorker"]


@dataclass
class JobWorker:
    """Pulls jobs from a queue and runs them via a handler registry.

    The worker is "running" once :meth:`start` is called; it claims
    jobs in a tight loop with a small sleep between empty polls.
    Stop with :meth:`stop` (graceful — drains the in-flight job
    before exiting).

    Pass ``in_process=True`` (default) to run the worker on a
    background thread of the calling process; for true multi-process
    deployments, instantiate one ``JobWorker`` per process and call
    :meth:`run_forever` from each.
    """

    queue: JobQueue
    handlers: Mapping[str, JobHandler]
    audit_log: AuditLog | None = None
    poll_interval_seconds: float = 0.5
    backoff_base_seconds: float = 5.0
    backoff_factor: float = 2.0
    name: str = "job-worker"
    _stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)

    # ---- runtime control -------------------------------------------

    def start(self) -> None:
        """Spawn a background thread that runs :meth:`run_forever`."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self.run_forever, daemon=True, name=self.name)
        self._thread.start()

    def stop(self, *, timeout: float = 10.0) -> None:
        """Ask the worker to stop after the current job finishes."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def run_forever(self) -> None:
        """Blocking loop: claim → execute → record. Returns on stop()."""
        while not self._stop.is_set():
            job = self.queue.claim()
            if job is None:
                self._stop.wait(self.poll_interval_seconds)
                continue
            self._execute_one(job)

    # ---- one job ---------------------------------------------------

    def run_one(self) -> Job | None:
        """Claim and execute one job. Returns None if queue empty.

        Useful for tests and CLI tools that want to drain the queue
        without spinning a thread.
        """
        job = self.queue.claim()
        if job is None:
            return None
        return self._execute_one(job)

    def _execute_one(self, job: Job) -> Job:
        handler = self.handlers.get(job.handler_name)
        if handler is None:
            attempt = JobAttempt(
                started_at=time.time(),
                finished_at=time.time(),
                ok=False,
                error=f"no handler registered for {job.handler_name!r}",
            )
            self._emit_audit(job, kind="fail", reason=attempt.error)
            return self.queue.fail(job.id, attempt=attempt)

        self._emit_audit(job, kind="start")
        started = time.time()
        try:
            result = handler(job.payload)
        except Exception as exc:
            finished = time.time()
            attempt = JobAttempt(
                started_at=started,
                finished_at=finished,
                ok=False,
                error=f"{type(exc).__name__}: {exc}"[:500],
            )
            backoff = self._backoff_for(job)
            updated = self.queue.fail(job.id, attempt=attempt, retry_in_seconds=backoff)
            self._emit_audit(
                job,
                kind="retry" if updated.state.value == "queued" else "fail",
                error=attempt.error,
                next_attempt_in=backoff,
                attempts=updated.n_attempts,
            )
            return updated
        finished = time.time()
        if not isinstance(result, JobResult):
            # Handlers SHOULD return JobResult; tolerate a bare value
            # by wrapping it.
            result = JobResult(output=result, output_preview=str(result)[:200])
        attempt = JobAttempt(
            started_at=started,
            finished_at=finished,
            ok=True,
            output_preview=result.output_preview[:500] if result.output_preview else None,
        )
        updated = self.queue.complete(job.id, attempt=attempt)
        self._emit_audit(
            job,
            kind="complete",
            duration_ms=int((finished - started) * 1000),
        )
        return updated

    def _backoff_for(self, job: Job) -> float:
        """Exponential: base * factor^(attempts_so_far)."""
        n = job.n_attempts  # n attempts before this one
        return self.backoff_base_seconds * (self.backoff_factor**n)

    def _emit_audit(self, job: Job, *, kind: str, **payload: Any) -> None:
        if self.audit_log is None:
            return
        # Best-effort audit: a transient sink failure must not block
        # the worker. Suppress everything; the chain's verify() job
        # picks up gaps separately.
        with contextlib.suppress(Exception):
            self.audit_log.emit(
                actor=f"job:{self.name}",
                action=f"job.{kind}",
                payload={
                    "job_id": job.id,
                    "handler": job.handler_name,
                    "tenant_id": job.tenant_id,
                    "parent_run_id": job.parent_run_id,
                    **payload,
                },
            )

    # ---- safety: requeue jobs orphaned by a crashed worker ---------

    def requeue_stale(self, *, older_than_seconds: float = 600.0) -> int:
        """Move RUNNING jobs whose attempt started > N seconds ago
        back to QUEUED. Run this on worker startup so a crashed
        previous worker's in-flight work is re-attempted.
        """
        try:
            running = self.queue.list(
                state=__import__("nom.jobs.types", fromlist=["JobState"]).JobState.RUNNING
            )
        except JobNotFoundError:
            return 0
        cutoff = time.time() - older_than_seconds
        n = 0
        for job in running:
            last = job.attempts[-1] if job.attempts else None
            stale = (last is None and job.queued_at < cutoff) or (
                last is not None and last.finished_at < cutoff
            )
            if not stale:
                continue
            self.queue.fail(
                job.id,
                attempt=JobAttempt(
                    started_at=last.started_at if last else job.queued_at,
                    finished_at=time.time(),
                    ok=False,
                    error="stale running job requeued by worker startup",
                ),
                retry_in_seconds=0.0,
            )
            n += 1
        return n
