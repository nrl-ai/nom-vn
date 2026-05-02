"""Built-in MCP tool catalog — credential-free starter tools.

These tools ship in the OSS package; they don't need any external
service credentials, so an operator can enable them on a fresh
install. Production deployments add credentialed integrations
(GitHub, Slack, SharePoint) via ``nom-vn-enterprise`` plugins.

Each tool here satisfies the ``nom.agents.Tool`` Protocol, so they
work both as MCP server tools (``nom mcp-serve``) and as direct
agent tools (``SingleAgent(tools=(...))``). One implementation,
two delivery surfaces.
"""

from __future__ import annotations

from nom.mcp.integrations.builtin import (
    CurrentTimeTool,
    FileGlobTool,
    JSONFieldTool,
    default_catalog,
)

__all__ = [
    "CurrentTimeTool",
    "FileGlobTool",
    "JSONFieldTool",
    "default_catalog",
]
