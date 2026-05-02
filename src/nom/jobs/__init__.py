"""``nom.jobs`` — background-job runtime with audit trail.

Three layers:

- :class:`Job` / :class:`JobState` — typed value objects describing
  one unit of work and its lifecycle.
- :class:`JobQueue` Protocol — pluggable storage. Default
  :class:`SQLiteJobQueue` is sufficient for Tier-S/M; production
  Tier-L deployments swap in a Postgres or Redis-backed queue.
- :class:`JobWorker` — pulls jobs, dispatches to a :class:`JobHandler`
  callable, records success / failure / retry. Single-process or
  process-pool.

Built-in job handlers cover the common paths a deployment needs the
moment it has more than one user:

- ``index_material`` — a chat space's material was uploaded; embed
  + chunk on the worker, leave the API request fast
- ``run_agent`` — long-running agent run (e.g. orchestrator-workers
  on a 100-page contract); user polls or subscribes via SSE
- ``export_dossier`` — render the technical dossier (Đ14.1.c) as a
  multi-page artifact

Every state transition is mirrored into an optional ``AuditLog`` so
the chain has the same record a regulator would want regardless of
whether the job ran inline or behind the queue.
"""

from __future__ import annotations

from nom.jobs.queue import (
    InMemoryJobQueue,
    JobNotFoundError,
    JobQueue,
    SQLiteJobQueue,
)
from nom.jobs.types import Job, JobAttempt, JobHandler, JobResult, JobState
from nom.jobs.worker import JobWorker

__all__ = [
    "InMemoryJobQueue",
    "Job",
    "JobAttempt",
    "JobHandler",
    "JobNotFoundError",
    "JobQueue",
    "JobResult",
    "JobState",
    "JobWorker",
    "SQLiteJobQueue",
]
