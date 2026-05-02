"""FastAPI routes for ``nom.agents``.

Wire any agent registry into the chat server::

    from nom.agents import SingleAgent, RAGTool
    from nom.agents_api import register_agent_routes

    app = build_app(...)
    register_agent_routes(
        app,
        agents={
            "legal_advisor": SingleAgent(...),
            "claims_processor": SingleAgent(...),
        },
    )

The endpoints respect the same gateway middleware as the rest of
``/api/*``: bearer / OIDC auth, ``current_user`` propagation, audit
correlation IDs.
"""

# NOTE: deliberately NO ``from __future__ import annotations`` — FastAPI
# resolves request-handler type hints at runtime to wire dependency
# injection (Request, Body, etc.). Stringised annotations break that
# (the routes will start treating ``Request`` as a query param).

from collections.abc import Mapping
from typing import Any

from nom.agents.protocol import Agent, Trace
from nom.agents_api.streaming import (
    StreamingTrace,
    sse_event,
    trace_event_to_sse,
)

__all__ = ["register_agent_routes"]


def register_agent_routes(app: "Any", *, agents: Mapping[str, Agent]) -> None:
    """Register ``/api/agents/*`` routes for the given agent registry.

    Two endpoints per registry:

    - ``POST /api/agents/{name}/run`` — request body
      ``{"task": "<question>"}``, response ``{"output": "...",
      "trace": [...], "n_tool_calls": N, "n_llm_calls": N}``.
    - ``GET /api/agents/{name}/stream?task=...`` — SSE stream of
      trace events; the final event is ``{"kind": "end", ...}``.

    The agent registry is captured by reference, so updating the
    map at runtime takes effect for subsequent requests (useful for
    EE admin consoles that hot-swap configurations).
    """
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse, StreamingResponse

    @app.get("/api/agents")  # type: ignore[misc]
    def list_agents() -> dict[str, Any]:
        return {
            "agents": [
                {
                    "name": name,
                    "type": type(agent).__name__,
                }
                for name, agent in agents.items()
            ]
        }

    @app.post("/api/agents/{name}/run")  # type: ignore[misc]
    def run_agent(name: str, body: Mapping[str, Any]) -> Any:
        agent = agents.get(name)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"agent {name!r} not found")
        task = body.get("task") if isinstance(body, Mapping) else None
        if not isinstance(task, str) or not task.strip():
            raise HTTPException(status_code=400, detail="`task` (str) is required")

        trace = Trace()
        try:
            result = agent.run(task, trace=trace)
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": f"agent error: {type(exc).__name__}: {exc}"},
            )
        return {
            "output": result.output if isinstance(result.output, str) else str(result.output),
            "trace": [trace_event_to_sse(e) for e in trace.events],
            "n_tool_calls": result.n_tool_calls,
            "n_llm_calls": result.n_llm_calls,
            "run_id": trace.run_id,
        }

    @app.get("/api/agents/{name}/stream")  # type: ignore[misc]
    def stream_agent(request: Request, name: str, task: str) -> Any:
        agent = agents.get(name)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"agent {name!r} not found")
        if not task.strip():
            raise HTTPException(status_code=400, detail="`task` query param required")

        trace = StreamingTrace()

        # Run the agent on a worker thread; the route streams events
        # from the queue. Errors land as a final 'error' event.
        import threading

        def _runner() -> None:
            try:
                agent.run(task, trace=trace)
            except Exception as exc:
                trace.emit(
                    "error",
                    agent=name,
                    exception=type(exc).__name__,
                    message=str(exc),
                )
                trace.emit("end", agent=name, ok=False)

        threading.Thread(target=_runner, daemon=True).start()

        def _gen() -> Any:
            # NB: do NOT set ``event=…`` per emission. Default events
            # surface via the browser's ``EventSource.onmessage``;
            # named events would need a separate addEventListener per
            # kind, which complicates the client. We carry the kind
            # in the JSON payload instead.
            yield sse_event({"kind": "stream_open", "agent": name, "run_id": trace.run_id})
            for ev in trace.iter_events(timeout=120):
                yield sse_event(trace_event_to_sse(ev))
            yield sse_event({"kind": "stream_close", "run_id": trace.run_id})

        return StreamingResponse(
            _gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # tell nginx not to buffer
                "Connection": "keep-alive",
            },
        )
