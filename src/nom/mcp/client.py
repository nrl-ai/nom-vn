"""MCP client — turn a remote MCP server into ``nom.agents.Tool``s.

Lets ``nom.agents.SingleAgent`` (and any pattern that takes a tool
list) consume external MCP servers. The client speaks JSON-RPC over
either stdio (subprocess) or HTTP. Every remote call is wrapped as
a :class:`MCPRemoteTool` that satisfies the ``Tool`` Protocol — the
agent runtime treats it like any other.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from nom.agents.protocol import Tool, ToolError
from nom.mcp.types import JSONRPC_VERSION, MCPTool

__all__ = ["MCPClient", "MCPClientError", "MCPRemoteTool", "make_remote_tools"]


class MCPClientError(RuntimeError):
    """The remote server returned a JSON-RPC error envelope."""


@dataclass
class MCPClient:
    """Talks JSON-RPC to one MCP server.

    ``transport`` is any callable: ``(message: dict) -> dict`` that
    sends one request and returns its response. Built-in factories
    (HTTP, stdio subprocess) live in :func:`http_transport` and
    :func:`stdio_transport`. Tests pass a lambda.
    """

    transport: Any  # Callable[[dict], dict]
    name: str = "remote"
    _next_id: int = field(default=1, init=False, repr=False)

    def call(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        message = {
            "jsonrpc": JSONRPC_VERSION,
            "id": self._next_id,
            "method": method,
            "params": dict(params or {}),
        }
        self._next_id += 1
        response = self.transport(message)
        if not isinstance(response, Mapping):
            msg = f"transport returned non-dict {type(response).__name__}"
            raise MCPClientError(msg)
        if "error" in response:
            err = response["error"]
            raise MCPClientError(f"{err.get('code', '?')}: {err.get('message', '')}")
        return response.get("result")

    def initialize(self) -> dict[str, Any]:
        return self.call("initialize") or {}

    def list_tools(self) -> tuple[MCPTool, ...]:
        result = self.call("tools/list") or {}
        items = result.get("tools") or []
        out: list[MCPTool] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            out.append(
                MCPTool(
                    name=str(item.get("name", "")),
                    description=str(item.get("description", "")),
                    input_schema=dict(item.get("inputSchema") or {}),
                )
            )
        return tuple(out)

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> str:
        result = (
            self.call(
                "tools/call",
                {"name": name, "arguments": dict(arguments)},
            )
            or {}
        )
        if result.get("isError"):
            content = result.get("content") or []
            text = " ".join(c.get("text", "") for c in content if isinstance(c, Mapping))
            raise ToolError(text or "remote tool returned isError")
        content = result.get("content") or []
        text_parts = [c.get("text", "") for c in content if isinstance(c, Mapping)]
        return "\n".join(text_parts).strip()


@dataclass
class MCPRemoteTool:
    """Wraps one remote MCP tool as a local :class:`nom.agents.Tool`.

    The agent runtime calls ``call(args)`` exactly the same way it
    calls a local tool; under the hood we proxy to the MCP server.
    Failures from the server raise :class:`ToolError` so the agent
    loop can retry.

    Fields are direct attributes (not @property) so this class
    satisfies the ``Tool`` Protocol — Protocol members are settable
    variables by default; read-only properties trip mypy on
    isinstance check.
    """

    client: MCPClient
    remote: MCPTool
    name: str = field(init=False)
    description: str = field(init=False)
    schema: Mapping[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        self.name = self.remote.name
        self.description = self.remote.description
        self.schema = self.remote.input_schema

    def call(self, args: Mapping[str, Any]) -> Any:
        return self.client.call_tool(self.remote.name, args)


def make_remote_tools(client: MCPClient) -> tuple[Tool, ...]:
    """Discover the server's tools and wrap each one as a local Tool."""
    return tuple(MCPRemoteTool(client=client, remote=t) for t in client.list_tools())


# --- transport factories --------------------------------------------


def http_transport(url: str, *, timeout: float = 30.0) -> Any:
    """Build a transport that POSTs each message to ``url``.

    The remote endpoint must accept JSON-RPC envelopes and return one
    envelope per request. Any HTTP error is surfaced as
    :class:`MCPClientError`.
    """

    def _send(message: dict[str, Any]) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:
            raise MCPClientError("httpx is required for HTTP transport") from exc
        try:
            r = httpx.post(url, json=message, timeout=timeout)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise MCPClientError(f"http error: {exc}") from exc
        try:
            data = r.json()
        except json.JSONDecodeError as exc:
            raise MCPClientError(f"non-JSON response: {exc}") from exc
        if not isinstance(data, dict):
            raise MCPClientError(f"expected JSON object, got {type(data).__name__}")
        return data

    return _send
