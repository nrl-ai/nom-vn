"""Core Protocol surface for ``nom.agents``.

The whole runtime is shaped around a tiny seam:

- :class:`Tool` — a callable with a JSON schema the LLM can target.
- :class:`Agent` — has a ``run(task) -> AgentResult`` method. Any
  pattern (single / chain / route / parallel / orchestrator /
  evaluator) is itself an Agent — composable.
- :class:`Trace` — append-only sequence of :class:`TraceEvent`,
  emitted alongside ``AgentResult`` and (optionally) shipped into
  ``nom.compliance.AuditLog``.

We deliberately avoid any LangChain-style ``BaseChatModel`` /
``Runnable`` / callback-handler superstructure (per design research:
the framework cost dwarfs the benefit). Tools are functions, agents
are objects with one method, traces are dataclasses.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "Agent",
    "AgentResult",
    "Tool",
    "ToolCall",
    "ToolError",
    "ToolResult",
    "Trace",
    "TraceEvent",
]


# ---------- Tools ----------------------------------------------------


class ToolError(Exception):
    """A tool call failed in a way the agent can recover from.

    Tools raise this when the failure is *expected* (network 429,
    file not found, validation reject) so the agent loop can feed
    the error back to the LLM and let it retry / pick another tool.
    Unexpected exceptions still propagate.
    """


@dataclass(frozen=True, slots=True)
class ToolCall:
    """An LLM-emitted tool invocation."""

    tool_name: str
    args: Mapping[str, Any]
    call_id: str = ""

    def __post_init__(self) -> None:
        if not self.call_id:
            object.__setattr__(self, "call_id", uuid.uuid4().hex[:12])


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The output of one ``ToolCall``.

    ``ok`` is True for success, False for a recoverable
    :class:`ToolError`. ``output`` is whatever the tool returns —
    typically a string the LLM can read; structured payloads are
    JSON-serialised by the runner before being fed back.
    """

    call_id: str
    ok: bool
    output: Any
    error: str | None = None
    elapsed_ms: float = 0.0


@runtime_checkable
class Tool(Protocol):
    """A callable the agent can invoke.

    Implementations must:
    - Be deterministic to whatever extent the underlying action allows.
    - Validate args defensively (LLMs hallucinate parameters).
    - Raise :class:`ToolError` for *expected* failures (so the agent
      can self-correct) and let unexpected exceptions propagate.

    ``schema`` is a JSON-Schema fragment describing ``args``. The
    runner uses it to render the tool list into the LLM prompt and
    to validate calls before dispatching.
    """

    name: str
    description: str
    schema: Mapping[str, Any]

    def call(self, args: Mapping[str, Any]) -> Any:
        """Execute the tool. Return arbitrary Python; the runner
        JSON-serialises the result before feeding it back to the LLM."""
        ...


# ---------- Trace ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """One observable thing happening during an agent run.

    Event ``kind`` is a short string from a small fixed set:

    - ``"start"`` — agent run began
    - ``"think"`` — model produced reasoning / decision text
    - ``"tool_call"`` — agent invoked a tool
    - ``"tool_result"`` — tool returned (ok or error)
    - ``"final"`` — agent emitted the final answer
    - ``"end"`` — run finished
    - ``"error"`` — run failed

    The schema is intentionally loose so new patterns can add
    informational events without breaking consumers — a UI just
    renders unknown kinds as a generic line.
    """

    ts: float
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Trace:
    """Append-only log of a single agent run.

    ``run_id`` ties to the gateway's correlation ID when the run is
    triggered via HTTP; ``audit_log`` (if set) writes mirror events
    into the chain-signed compliance audit so a regulator can replay
    the same run a year later.
    """

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    events: list[TraceEvent] = field(default_factory=list)

    def emit(self, kind: str, **payload: Any) -> TraceEvent:
        ev = TraceEvent(ts=time.time(), kind=kind, payload=payload)
        self.events.append(ev)
        return ev


# ---------- Agent ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Outcome of one agent run."""

    output: Any
    trace: Trace
    n_tool_calls: int = 0
    n_llm_calls: int = 0
    final_state: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Agent(Protocol):
    """Anything that can ``run`` an task and return an :class:`AgentResult`.

    Patterns (Single / Chain / Route / Parallel / Orchestrator /
    Evaluator) all implement this — so they nest cleanly: an
    OrchestratorWorkers can route to a SingleAgent, which can call
    a tool that's itself another OrchestratorWorkers.
    """

    name: str

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        """Execute one task. ``task`` is the user-supplied prompt /
        question / instruction. ``trace`` is reused when called as a
        sub-agent so events flow into the parent run's log."""
        ...
