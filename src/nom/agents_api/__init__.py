"""HTTP routes that expose ``nom.agents`` over the existing FastAPI app.

Two endpoints:

- ``POST /api/agents/{name}/run`` — synchronous run, returns final answer + trace
- ``GET /api/agents/{name}/stream?task=...`` — Server-Sent Events stream
  (the ``agent2ui`` protocol) emitting trace events as they happen

The streaming endpoint is what a UI subscribes to so users see the
agent's reasoning, tool calls, and final answer as they unfold —
not as one big batch at the end. This is "agent2ui" in the project
plan.

The agent registry is dependency-injected at app build time so
deployers wire whatever agents they want into the same FastAPI app
their chat UI already runs on.
"""

from __future__ import annotations

from nom.agents_api.routes import register_agent_routes
from nom.agents_api.streaming import (
    StreamingTrace,
    sse_event,
    trace_event_to_sse,
)

__all__ = [
    "StreamingTrace",
    "register_agent_routes",
    "sse_event",
    "trace_event_to_sse",
]
