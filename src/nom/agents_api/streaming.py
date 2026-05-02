"""SSE encoding for agent traces — the ``agent2ui`` wire protocol.

A :class:`StreamingTrace` subclasses ``Trace``: every ``emit`` pushes
the event onto an in-memory queue *and* appends to ``events`` (so
the ``AgentResult`` returned at the end carries the same log a
non-streaming run would). The HTTP route reads from the queue and
yields SSE-formatted bytes to the client.

The producer-consumer split lets us run the agent in a worker thread
and stream events over an asyncio response without rewriting the
runtime. Backpressure: the queue is unbounded — UIs read fast; if
they don't, slow consumer is the operator's problem to solve, not
the runtime's.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from nom.agents.protocol import Trace, TraceEvent

__all__ = [
    "StreamingTrace",
    "sse_event",
    "trace_event_to_sse",
]


@dataclass
class StreamingTrace(Trace):
    """``Trace`` that also writes every event into a queue.

    Use:

        trace = StreamingTrace()
        # producer thread:
        threading.Thread(target=lambda: agent.run(task, trace=trace)).start()
        # consumer:
        for ev in trace.iter_events(timeout=30):
            yield sse_event(trace_event_to_sse(ev))
    """

    _queue: queue.Queue[TraceEvent | None] = field(
        default_factory=queue.Queue, init=False, repr=False
    )
    _done: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def emit(self, kind: str, **payload: Any) -> TraceEvent:
        ev = super().emit(kind, **payload)
        self._queue.put(ev)
        if kind == "end":
            # Sentinel so the consumer loop exits.
            self._queue.put(None)
            self._done.set()
        return ev

    def iter_events(self, *, timeout: float | None = None) -> Iterator[TraceEvent]:
        """Yield events as the agent emits them. Stops when the agent
        emits an ``end`` event (or after ``timeout`` seconds total).
        """
        deadline = (time.monotonic() + timeout) if timeout is not None else None
        while True:
            remaining = None
            if deadline is not None:
                remaining = max(0.0, deadline - time.monotonic())
                if remaining == 0.0:
                    return
            try:
                ev = self._queue.get(timeout=remaining)
            except queue.Empty:
                return
            if ev is None:
                return
            yield ev


def trace_event_to_sse(event: TraceEvent) -> dict[str, Any]:
    """Lower a ``TraceEvent`` to a JSON-safe dict for SSE.

    UIs consume this directly. We deliberately don't expose internal
    object ids — only the fields a viewer needs to render.
    """
    return {
        "ts": event.ts,
        "kind": event.kind,
        "payload": dict(event.payload),
    }


def sse_event(
    data: dict[str, Any], *, event: str | None = None, event_id: str | None = None
) -> bytes:
    """Format one SSE message line.

    Per the SSE spec: each ``data:`` line + double newline = one
    event. We send the JSON in a single ``data:`` line; UIs ``JSON.parse``
    after stripping the prefix.
    """
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines).encode("utf-8")
