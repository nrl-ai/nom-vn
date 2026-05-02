"""Value types for ``nom.jobs``.

Job lifecycle:

    queued ──► running ──► succeeded
                  │
                  └────► failed
                           │
                           └────► (retry on exponential backoff,
                                   up to ``max_attempts``)
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "Job",
    "JobAttempt",
    "JobHandler",
    "JobResult",
    "JobState",
]


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class JobAttempt:
    """One attempt at executing a job.

    A job may have multiple attempts when retries are enabled; the
    queue stores them in time order so an operator inspecting a
    failed job sees the full history.
    """

    started_at: float
    finished_at: float
    ok: bool
    error: str | None = None
    output_preview: str | None = None


@dataclass(frozen=True, slots=True)
class Job:
    """A unit of work the queue is responsible for executing.

    ``handler_name`` is the registry key under which the worker
    looks up a callable. ``payload`` is whatever the handler expects;
    canonical-JSON-serialisable so storage round-trips losslessly.
    """

    id: str
    handler_name: str
    payload: Mapping[str, Any]
    state: JobState
    queued_at: float
    available_at: float  # first-attempt time; bumped on retry backoff
    max_attempts: int = 3
    tenant_id: str | None = None
    parent_run_id: str | None = None  # ties to agent runs / correlation IDs
    attempts: tuple[JobAttempt, ...] = ()

    @classmethod
    def new(
        cls,
        *,
        handler_name: str,
        payload: Mapping[str, Any],
        max_attempts: int = 3,
        tenant_id: str | None = None,
        parent_run_id: str | None = None,
        scheduled_for: float | None = None,
    ) -> Job:
        now = time.time()
        return cls(
            id=uuid.uuid4().hex[:16],
            handler_name=handler_name,
            payload=dict(payload),
            state=JobState.QUEUED,
            queued_at=now,
            available_at=scheduled_for if scheduled_for is not None else now,
            max_attempts=max_attempts,
            tenant_id=tenant_id,
            parent_run_id=parent_run_id,
        )

    @property
    def n_attempts(self) -> int:
        return len(self.attempts)

    def to_row(self) -> dict[str, Any]:
        """Serialise for the SQLite store (or any JSON-friendly sink)."""
        return {
            "id": self.id,
            "handler_name": self.handler_name,
            "payload_json": json.dumps(dict(self.payload), ensure_ascii=False),
            "state": self.state.value,
            "queued_at": self.queued_at,
            "available_at": self.available_at,
            "max_attempts": self.max_attempts,
            "tenant_id": self.tenant_id,
            "parent_run_id": self.parent_run_id,
            "attempts_json": json.dumps(
                [
                    {
                        "started_at": a.started_at,
                        "finished_at": a.finished_at,
                        "ok": a.ok,
                        "error": a.error,
                        "output_preview": a.output_preview,
                    }
                    for a in self.attempts
                ],
                ensure_ascii=False,
            ),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Job:
        attempts: tuple[JobAttempt, ...]
        attempts_raw = json.loads(row.get("attempts_json") or "[]")
        attempts = tuple(JobAttempt(**a) for a in attempts_raw)
        return cls(
            id=str(row["id"]),
            handler_name=str(row["handler_name"]),
            payload=json.loads(row.get("payload_json") or "{}"),
            state=JobState(row["state"]),
            queued_at=float(row["queued_at"]),
            available_at=float(row["available_at"]),
            max_attempts=int(row.get("max_attempts", 3)),
            tenant_id=row.get("tenant_id"),
            parent_run_id=row.get("parent_run_id"),
            attempts=attempts,
        )


@dataclass(frozen=True, slots=True)
class JobResult:
    """What a :class:`JobHandler` returns.

    ``output`` is the handler's payload — anything canonical-JSON-able.
    The worker stores a short preview in the audit chain; full output
    lives wherever the handler writes it (DB row, file, etc.).
    """

    output: Any = None
    output_preview: str = ""


@runtime_checkable
class JobHandler(Protocol):
    """Callable that executes one job.

    Implementations should:
    - Be deterministic w.r.t. the payload (idempotent under retry).
    - Raise on transient failure → the worker retries with backoff.
    - Surface terminal errors with a clear message.
    """

    def __call__(self, payload: Mapping[str, Any]) -> JobResult: ...
