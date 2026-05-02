"""Tests for ``nom.mcp`` — server, client, and round-trip integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from nom.agents.protocol import Tool, ToolError
from nom.mcp import MCPClient, MCPClientError, MCPServer
from nom.mcp.client import make_remote_tools

# ---------- a tiny in-process Tool for testing -----------------------


class _EchoTool:
    name = "echo"
    description = "Echo back the message field."
    schema: Mapping[str, Any] = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    def call(self, args: Mapping[str, Any]) -> Any:
        if "message" not in args:
            raise ToolError("`message` is required")
        return f"echo: {args['message']}"


class _BoomTool:
    name = "boom"
    description = "Always raises."
    schema: Mapping[str, Any] = {"type": "object"}

    def call(self, args: Mapping[str, Any]) -> Any:
        raise ToolError("expected boom")


# ---------- protocol checks ------------------------------------------


def test_tool_protocol_compatibility() -> None:
    assert isinstance(_EchoTool(), Tool)


# ---------- server ---------------------------------------------------


@pytest.fixture
def server() -> MCPServer:
    return MCPServer(tools=(_EchoTool(), _BoomTool()))


def test_initialize_returns_server_info(server: MCPServer) -> None:
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    r = server.handle_message(msg)
    assert r is not None
    assert r["result"]["serverInfo"]["name"] == "nom-vn"
    assert "tools" in r["result"]["capabilities"]


def test_tools_list_enumerates(server: MCPServer) -> None:
    r = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert r is not None
    names = [t["name"] for t in r["result"]["tools"]]
    assert names == ["echo", "boom"]


def test_tools_call_success(server: MCPServer) -> None:
    r = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"message": "hi"}},
        }
    )
    assert r is not None
    assert r["result"]["isError"] is False
    assert r["result"]["content"][0]["text"] == "echo: hi"


def test_tools_call_tool_error_returns_iserror(server: MCPServer) -> None:
    r = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "boom", "arguments": {}},
        }
    )
    assert r is not None
    assert r["result"]["isError"] is True
    assert "expected boom" in r["result"]["content"][0]["text"]


def test_tools_call_unknown_returns_invalid_params(server: MCPServer) -> None:
    r = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "ghost", "arguments": {}},
        }
    )
    assert r is not None
    assert r["error"]["code"] == -32602  # invalid params
    assert "ghost" in r["error"]["message"]


def test_unknown_method_returns_method_not_found(server: MCPServer) -> None:
    r = server.handle_message({"jsonrpc": "2.0", "id": 6, "method": "tools/exotic"})
    assert r is not None
    assert r["error"]["code"] == -32601


def test_notification_returns_none(server: MCPServer) -> None:
    """No id → no response (JSON-RPC notification)."""
    r = server.handle_message({"jsonrpc": "2.0", "method": "ping"})
    assert r is None


def test_invalid_message_shape() -> None:
    r = MCPServer().handle_message("not an object")  # type: ignore[arg-type]
    assert r is not None
    assert r["error"]["code"] == -32600


# ---------- client ---------------------------------------------------


def _bound_transport(server: MCPServer) -> Any:
    """In-process transport piping client → server.handle_message."""

    def _send(message: dict[str, Any]) -> dict[str, Any]:
        out = server.handle_message(message)
        if out is None:
            return {"jsonrpc": "2.0", "id": message.get("id"), "result": None}
        return out

    return _send


def test_client_initialize(server: MCPServer) -> None:
    c = MCPClient(transport=_bound_transport(server))
    info = c.initialize()
    assert info["serverInfo"]["name"] == "nom-vn"


def test_client_list_tools_and_call_round_trip(server: MCPServer) -> None:
    c = MCPClient(transport=_bound_transport(server))
    tools = c.list_tools()
    assert {t.name for t in tools} == {"echo", "boom"}
    out = c.call_tool("echo", {"message": "xin chào"})
    assert "xin chào" in out


def test_client_propagates_iserror_as_toolerror(server: MCPServer) -> None:
    c = MCPClient(transport=_bound_transport(server))
    with pytest.raises(ToolError, match="expected boom"):
        c.call_tool("boom", {})


def test_client_raises_on_rpc_error(server: MCPServer) -> None:
    c = MCPClient(transport=_bound_transport(server))
    with pytest.raises(MCPClientError, match="ghost"):
        c.call_tool("ghost", {})


# ---------- end-to-end: agent uses MCP-backed remote tool ------------


def test_single_agent_consumes_remote_mcp_tool(server: MCPServer) -> None:
    """Round-trip: SingleAgent → MCPRemoteTool → MCPClient → MCPServer →
    real Tool. Proves nom.agents can use external MCP servers natively."""
    from nom.agents import SingleAgent
    from tests.test_agents import _ScriptedLLM

    client = MCPClient(transport=_bound_transport(server))
    remote_tools = make_remote_tools(client)
    assert {t.name for t in remote_tools} == {"echo", "boom"}

    llm = _ScriptedLLM(
        [
            {
                "thought": "use remote echo",
                "action": "tool_call",
                "tool_name": "echo",
                "tool_args": {"message": "vui lòng chào"},
            },
            {
                "thought": "got it",
                "action": "final",
                "final_answer": "Đã echo qua MCP.",
            },
        ]
    )
    agent = SingleAgent(name="mcp_agent", llm=llm, tools=remote_tools)
    r = agent.run("Echo dùm tôi")
    assert "Đã echo" in r.output
    assert r.n_tool_calls == 1
    # Verify the trace recorded the MCP-backed tool result
    tr = next(e for e in r.trace.events if e.kind == "tool_result")
    assert "echo: vui lòng chào" in str(tr.payload["output"])
