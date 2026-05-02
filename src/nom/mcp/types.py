"""Wire types for ``nom.mcp``.

A subset of the MCP spec — enough to register and call tools,
list capabilities, and exchange JSON-RPC envelopes. Extending later
(prompts, sampling, completion) is additive.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "JSONRPC_VERSION",
    "MCPError",
    "MCPRequest",
    "MCPResponse",
    "MCPTool",
    "MCPToolResult",
]


JSONRPC_VERSION = "2.0"


@dataclass(frozen=True, slots=True)
class MCPTool:
    """Describes one tool a server exposes.

    ``input_schema`` is a JSON-Schema object (the MCP spec calls it
    ``inputSchema`` on the wire — we serialise that way). ``name`` is
    the canonical handle clients call.
    """

    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)

    def to_wire(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": dict(self.input_schema) if self.input_schema else {"type": "object"},
        }


@dataclass(frozen=True, slots=True)
class MCPToolResult:
    """Result of a single ``tools/call`` request.

    ``content`` is a list per the MCP spec, but we ship a single
    text block in 99% of cases. ``is_error`` flags failure without
    needing JSON-RPC error envelopes (those are reserved for protocol
    errors, not tool errors).
    """

    text: str
    is_error: bool = False

    def to_wire(self) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": self.text}],
            "isError": self.is_error,
        }


@dataclass(frozen=True, slots=True)
class MCPRequest:
    """Inbound JSON-RPC request envelope."""

    method: str
    params: Mapping[str, Any] = field(default_factory=dict)
    id: int | str | None = None

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> MCPRequest:
        return cls(
            method=str(data.get("method", "")),
            params=dict(data.get("params") or {}),
            id=data.get("id"),
        )


@dataclass(frozen=True, slots=True)
class MCPResponse:
    """Outbound JSON-RPC response envelope."""

    id: int | str | None
    result: Any = None
    error: MCPError | None = None

    def to_wire(self) -> dict[str, Any]:
        env: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": self.id}
        if self.error is not None:
            env["error"] = {
                "code": self.error.code,
                "message": self.error.message,
            }
            if self.error.data is not None:
                env["error"]["data"] = self.error.data
        else:
            env["result"] = self.result
        return env


@dataclass(frozen=True, slots=True)
class MCPError:
    """JSON-RPC error body. Codes follow the spec:

    - -32600 Invalid Request
    - -32601 Method not found
    - -32602 Invalid params
    - -32603 Internal error
    """

    code: int
    message: str
    data: Any = None
