"""Per-request user context — propagated to audit emission.

``ContextVar`` lets us thread the authenticated user through the call
stack without changing the LLM Protocol signature. Gateway middleware
sets ``current_user`` after authenticating; ``AuditedLLM`` reads it
when constructing ``actor=`` so audit events become
``user:nguyen.va@bank.vn|llm:qwen3:8b`` instead of just the model
name.

ContextVar is task-safe under asyncio (each Task gets its own copy)
and thread-safe — switching threads inherits the parent's value
unless explicitly reset.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nom.platform.types import User

__all__ = ["current_user", "set_current_user"]


current_user: ContextVar[User | None] = ContextVar("nom_current_user", default=None)
"""The authenticated user for the current request / task, or None.

Read this from ``AuditedLLM`` / ``AuditedRAG`` to attribute model
calls to the user who triggered them. ``None`` means the call was
made outside any authenticated context (CLI, batch job, test) — in
that case audit emission falls back to the ``llm:<name>`` actor
form.
"""


def set_current_user(user: User | None) -> None:
    """Set the current user for this task / thread.

    Convenience wrapper for ``current_user.set(user)``. Use the
    returned token from ``ContextVar.set()`` directly when you need
    to reset the value at scope exit; this helper is for the common
    "set once at request entry" path.
    """
    current_user.set(user)
