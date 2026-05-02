"""MCP server — exposes ``nom.agents.Tool`` instances to MCP clients.

Speaks JSON-RPC 2.0; transport-agnostic. The ``handle_message`` API
takes a parsed dict, returns a dict — wire that into stdio, HTTP/SSE,
WebSocket, or anything else without rewriting protocol logic.

Methods supported (subset of the MCP spec sufficient for tool use):

- ``initialize`` — handshake. Reports server name + capabilities.
- ``tools/list`` — enumerate registered tools.
- ``tools/call`` — invoke one tool.
- ``ping`` — health check.

Audit: every ``tools/call`` lands in the configured ``AuditLog`` (when
provided) so an inspector replays the same chain whether the call
came in via the HTTP gateway or via MCP.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nom.agents.protocol import Tool, ToolError
from nom.mcp.types import (
    MCPError,
    MCPRequest,
    MCPResponse,
    MCPTool,
    MCPToolResult,
)

if TYPE_CHECKING:
    from nom.compliance.audit.log import AuditLog

__all__ = ["MCPServer"]


# JSON-RPC error codes per spec.
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


@dataclass
class MCPServer:
    """Serve a set of ``nom.agents.Tool`` instances over MCP.

    Construct with whatever tool catalogue the deployment wants
    exposed. ``audit_log`` is optional but recommended in production:
    every successful or failed ``tools/call`` lands in the
    chain-signed audit so MCP traffic is regulator-replayable.
    """

    server_name: str = "nom-vn"
    server_version: str = "0.3.0a1"
    tools: tuple[Tool, ...] = ()
    audit_log: AuditLog | None = None
    _by_name: dict[str, Tool] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._by_name = {t.name: t for t in self.tools}

    # --- public ------------------------------------------------------

    def handle_message(self, message: Mapping[str, Any]) -> dict[str, Any] | None:
        """Process one inbound JSON-RPC message; return the response.

        Returns ``None`` for notifications (per JSON-RPC spec — when
        the message has no ``id``, no response is expected).
        """
        if not isinstance(message, Mapping):
            return MCPResponse(
                id=None,
                error=MCPError(_INVALID_REQUEST, "request must be a JSON object"),
            ).to_wire()

        req = MCPRequest.from_wire(message)
        is_notification = req.id is None

        try:
            result = self._dispatch(req)
        except _RpcError as exc:
            if is_notification:
                return None
            return MCPResponse(id=req.id, error=exc.to_error()).to_wire()
        except Exception as exc:
            if is_notification:
                return None
            return MCPResponse(
                id=req.id,
                error=MCPError(_INTERNAL_ERROR, f"internal error: {exc}"),
            ).to_wire()

        if is_notification:
            return None
        return MCPResponse(id=req.id, result=result).to_wire()

    # --- transport adapters -----------------------------------------

    def serve_stdio(self) -> None:
        """Run a blocking stdio loop — Claude Desktop / Cursor MCP."""
        import sys

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = self.handle_message(msg)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()

    # --- internal dispatch ------------------------------------------

    def _dispatch(self, req: MCPRequest) -> Any:
        if req.method == "initialize":
            return self._initialize()
        if req.method == "tools/list":
            return self._list_tools()
        if req.method == "tools/call":
            return self._call_tool(req.params)
        if req.method == "ping":
            return {}
        msg = f"method {req.method!r} not implemented"
        raise _RpcError(_METHOD_NOT_FOUND, msg)

    def _initialize(self) -> dict[str, Any]:
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": self.server_name,
                "version": self.server_version,
            },
            "capabilities": {
                "tools": {},
            },
        }

    def _list_tools(self) -> dict[str, Any]:
        return {
            "tools": [
                MCPTool(
                    name=t.name,
                    description=t.description,
                    input_schema=dict(t.schema or {"type": "object"}),
                ).to_wire()
                for t in self.tools
            ]
        }

    def _call_tool(self, params: Mapping[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(name, str) or not name:
            raise _RpcError(_INVALID_PARAMS, "params.name (str) is required")
        if not isinstance(args, Mapping):
            raise _RpcError(_INVALID_PARAMS, "params.arguments must be an object")

        tool = self._by_name.get(name)
        if tool is None:
            available = sorted(self._by_name)
            raise _RpcError(
                _INVALID_PARAMS,
                f"unknown tool {name!r}; available: {available}",
            )

        result, audit_payload = self._invoke(tool, args)
        if self.audit_log is not None:
            self.audit_log.emit(
                actor=f"mcp:{self.server_name}",
                action="mcp.tools.call",
                payload=audit_payload,
            )
        return result.to_wire()

    def _invoke(self, tool: Tool, args: Mapping[str, Any]) -> tuple[MCPToolResult, dict[str, Any]]:
        try:
            output = tool.call(args)
        except ToolError as exc:
            return (
                MCPToolResult(text=str(exc), is_error=True),
                {"tool": tool.name, "ok": False, "error": str(exc)},
            )
        text = self._serialise(output)
        return (
            MCPToolResult(text=text, is_error=False),
            {"tool": tool.name, "ok": True, "output_len": len(text)},
        )

    @staticmethod
    def _serialise(output: Any) -> str:
        if isinstance(output, str):
            return output
        try:
            return json.dumps(output, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return repr(output)


@dataclass
class _RpcError(Exception):
    code: int
    message: str

    def to_error(self) -> MCPError:
        return MCPError(code=self.code, message=self.message)
