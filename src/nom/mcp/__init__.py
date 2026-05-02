"""``nom.mcp`` — Model Context Protocol bridge.

Two roles:

- :mod:`nom.mcp.server` — expose ``nom.rag`` / ``nom.doc`` / ``nom.text`` /
  ``nom.nlp`` as MCP tools so any MCP client (Claude Desktop, Cursor,
  Zed, custom agents) can call them as if they were native skills.
- :mod:`nom.mcp.client` — let ``nom.agents`` consume external MCP
  servers, turning each remote tool into a :class:`nom.agents.Tool`
  with audit-tracked invocations.

We deliberately implement a minimal MCP transport (JSON-RPC over
stdio + HTTP/SSE) rather than depend on the official ``mcp`` SDK.
Reasons:

1. **No new heavy deps** — the official SDK pulls in pydantic-settings,
   anyio extras, and a websocket stack we don't otherwise need.
2. **Audit-first** — every tool call must go through ``AuditedLLM`` /
   ``AuditLog``; wrapping the official SDK's transport requires
   bridging callbacks. Our small native impl writes to the chain
   directly.
3. **VN gotchas** — schema fields with VN diacritics need NFC-safe
   JSON. Easier to control end-to-end.

The wire format conforms to the MCP spec at the message level so
clients are interoperable.
"""

from __future__ import annotations

from nom.mcp.client import MCPClient, MCPClientError
from nom.mcp.server import MCPServer
from nom.mcp.types import (
    MCPRequest,
    MCPResponse,
    MCPTool,
    MCPToolResult,
)

__all__ = [
    "MCPClient",
    "MCPClientError",
    "MCPRequest",
    "MCPResponse",
    "MCPServer",
    "MCPTool",
    "MCPToolResult",
]
