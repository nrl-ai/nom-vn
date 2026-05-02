"""Tests for the HTTP surface of ``nom.agents`` — sync ``/run`` plus
SSE ``/stream`` (the agent2ui protocol).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nom.agents import SingleAgent
from nom.agents_api import register_agent_routes
from tests.test_agents import _ScriptedLLM


def _make_app() -> tuple[FastAPI, dict[str, Any]]:
    """Build a minimal FastAPI app with one agent wired in."""
    app = FastAPI()
    llm = _ScriptedLLM(
        [
            {
                "thought": "answer directly",
                "action": "final",
                "final_answer": "Theo Hiến pháp 2013 Điều 26.",
            }
        ]
        * 10  # plenty for repeated runs in tests
    )
    agent = SingleAgent(name="legal", llm=llm)
    register_agent_routes(app, agents={"legal": agent})
    return app, {"llm": llm, "agent": agent}


def test_list_agents() -> None:
    app, _ = _make_app()
    c = TestClient(app)
    r = c.get("/api/agents")
    assert r.status_code == 200
    names = [a["name"] for a in r.json()["agents"]]
    assert "legal" in names


def test_run_returns_output_and_trace() -> None:
    app, _ = _make_app()
    c = TestClient(app)
    r = c.post("/api/agents/legal/run", json={"task": "Hiến pháp 2013 nói gì?"})
    assert r.status_code == 200
    data = r.json()
    assert "Điều 26" in data["output"]
    assert data["n_llm_calls"] == 1
    kinds = [e["kind"] for e in data["trace"]]
    assert "start" in kinds
    assert "final" in kinds
    assert "end" in kinds


def test_run_404_for_unknown_agent() -> None:
    app, _ = _make_app()
    c = TestClient(app)
    r = c.post("/api/agents/ghost/run", json={"task": "x"})
    assert r.status_code == 404
    assert "ghost" in r.json()["detail"]


def test_run_400_on_empty_task() -> None:
    app, _ = _make_app()
    c = TestClient(app)
    r = c.post("/api/agents/legal/run", json={"task": "   "})
    assert r.status_code == 400


def test_stream_emits_sse_events() -> None:
    """Hit /stream and parse the SSE messages — verify we see at least
    start, final, end events for the agent run."""
    app, _ = _make_app()
    c = TestClient(app)
    with c.stream("GET", "/api/agents/legal/stream", params={"task": "test"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes()).decode("utf-8")

    events = _parse_sse(body)
    kinds = [e["payload"]["kind"] for e in events if "kind" in e["payload"]]
    assert "start" in kinds
    assert "final" in kinds
    # Should include either the runtime's 'end' event or the route's 'stream_close'
    assert any(k in {"end", "stream_close"} for k in kinds)


def test_stream_404_for_unknown_agent() -> None:
    app, _ = _make_app()
    c = TestClient(app)
    r = c.get("/api/agents/ghost/stream", params={"task": "x"})
    assert r.status_code == 404


def _parse_sse(text: str) -> list[dict[str, Any]]:
    """Parse SSE wire format into a list of {'event': str, 'payload': dict}."""
    events: list[dict[str, Any]] = []
    cur: dict[str, Any] = {}
    for raw in text.splitlines():
        if raw == "":
            if cur:
                events.append(cur)
                cur = {}
            continue
        if raw.startswith("event:"):
            cur["event"] = raw.removeprefix("event:").strip()
        elif raw.startswith("data:"):
            data_str = raw.removeprefix("data:").strip()
            try:
                cur["payload"] = json.loads(data_str)
            except json.JSONDecodeError:
                cur["payload"] = {"raw": data_str}
    if cur:
        events.append(cur)
    return events
