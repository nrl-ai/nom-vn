"""Tests for the ``nom mcp-serve`` and ``nom worker`` CLI surfaces.

We don't actually fork a subprocess — instead we exercise the same
helper functions the CLI dispatchers call, so the test stays in
the same Python interpreter and is fast/deterministic.
"""

from __future__ import annotations

from pathlib import Path

from nom.agents.protocol import Tool
from nom.chat.cli import _build_nlp_tools
from nom.mcp import MCPClient, MCPServer


def test_nlp_tools_satisfy_protocol() -> None:
    for t in _build_nlp_tools():
        assert isinstance(t, Tool)


def test_mcp_serves_nlp_tools_round_trip() -> None:
    """Build the same tool set the CLI's mcp-serve uses, hand it to
    an MCPServer, and round-trip through MCPClient. Proves the CLI
    integration end-to-end without subprocess overhead."""
    server = MCPServer(server_name="nom-vn", tools=tuple(_build_nlp_tools()))

    def transport(message: dict) -> dict:
        out = server.handle_message(message)
        if out is None:
            return {"jsonrpc": "2.0", "id": message.get("id"), "result": None}
        return out

    client = MCPClient(transport=transport)

    info = client.initialize()
    assert info["serverInfo"]["name"] == "nom-vn"

    tools = client.list_tools()
    names = {t.name for t in tools}
    assert names == {"vn_extract_entities", "vn_sentiment", "detect_language"}

    out = client.call_tool("vn_sentiment", {"text": "Sản phẩm rất tuyệt vời"})
    assert "positive" in out

    out = client.call_tool("detect_language", {"text": "Đây là tiếng Việt"})
    assert '"language": "vi"' in out

    out = client.call_tool("vn_extract_entities", {"text": "VCB ngày 02/05/2026"})
    assert "ORG" in out
    assert "DATE" in out


def test_worker_command_runs_with_no_handlers(tmp_path: Path) -> None:
    """The CLI worker should drain an empty queue gracefully — no
    handlers needed at start-up time. Operators register handlers
    by importing the worker programmatically; this command is just
    the runtime."""
    from nom.jobs import JobWorker, SQLiteJobQueue

    queue = SQLiteJobQueue(db_path=tmp_path / "jobs.sqlite")
    worker = JobWorker(queue=queue, handlers={}, poll_interval_seconds=0.01)
    # No jobs queued — claim returns None.
    assert worker.run_one() is None
