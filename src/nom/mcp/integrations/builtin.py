"""Credential-free MCP integration tools.

These cover the common "agent needs to inspect the local filesystem
or get the current time" cases that every deployment hits in the
first hour. None of them touch external services; production
integrations (GitHub, Slack, SharePoint, …) ship in ``nom-vn-enterprise``.

Tools:

- :class:`FileGlobTool` — list files matching a glob inside an
  allow-listed root. Pairs with :class:`nom.agents.tools.builtin.FileReadTool`
  to give an agent a "find then read" workflow.
- :class:`JSONFieldTool` — read a specific JSON path from a file
  inside an allow-listed root. Useful for config / manifest lookups
  the agent can use to ground its answer.
- :class:`CurrentTimeTool` — return the current ISO 8601 UTC
  timestamp. The most commonly mis-hallucinated fact in any agent
  prompt; this fixes it.

Plus :func:`default_catalog` — a sensible bundle for ``nom mcp-serve``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

from nom.agents.protocol import ToolError

__all__ = [
    "CurrentTimeTool",
    "FileGlobTool",
    "JSONFieldTool",
    "default_catalog",
]


@dataclass
class FileGlobTool:
    """List files matching ``pattern`` under ``root``.

    Pattern uses :meth:`pathlib.Path.glob` semantics (``**`` matches
    nested directories). Path traversal blocked: the resolved root
    is the boundary; any pattern that resolves outside it is
    rejected.
    """

    root: Path
    max_results: int = 200
    name: str = "file_glob"
    description: str = (
        "List filenames under the configured root that match a glob "
        "pattern. Returns up to max_results paths, relative to the root. "
        "Use ** to recurse (e.g. 'src/**/*.py')."
    )
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern. Examples: '*.md', 'src/**/*.py'.",
            }
        },
        "required": ["pattern"],
    }

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()

    def call(self, args: Mapping[str, Any]) -> Any:
        pattern = args.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ToolError("`pattern` is required and must be a non-empty string")
        # Reject absolute patterns and parent-traversal patterns.
        if pattern.startswith("/") or ".." in Path(pattern).parts:
            raise ToolError("pattern must be relative and must not contain '..' segments")

        matches: list[str] = []
        for p in self.root.glob(pattern):
            if not self._under_root(p):
                continue
            try:
                rel = p.relative_to(self.root).as_posix()
            except ValueError:
                continue
            matches.append(rel)
            if len(matches) >= self.max_results:
                break
        matches.sort()
        return {"root": str(self.root), "pattern": pattern, "matches": matches}

    def _under_root(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.root)
        except ValueError:
            return False
        return True


@dataclass
class JSONFieldTool:
    """Read one field from a JSON file under ``root`` via dotted path.

    Supports ``a.b.c`` path notation; integer segments index into
    arrays (``items.0.name``). Returns the value plus type info so
    the LLM doesn't need to second-guess. The full file content
    isn't returned — just the requested field — so agents can use
    this on large config files without blowing the LLM context.
    """

    root: Path
    name: str = "json_field"
    description: str = (
        "Read a single field from a JSON file inside the configured "
        "root. Use dotted paths ('a.b.c') and integer segments for "
        "array indices ('items.0.name')."
    )
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "JSON file path relative to root."},
            "field": {
                "type": "string",
                "description": "Dotted path to the field, or empty string for the whole document.",
            },
        },
        "required": ["path"],
    }

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()

    def call(self, args: Mapping[str, Any]) -> Any:
        path_arg = args.get("path")
        field = args.get("field", "")
        if not isinstance(path_arg, str) or not path_arg:
            raise ToolError("`path` is required")
        if not isinstance(field, str):
            raise ToolError("`field` must be a string")
        candidate = (self.root / path_arg).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ToolError(f"path escapes root: {path_arg!r}") from exc
        if not candidate.exists():
            raise ToolError(f"file not found: {path_arg!r}")
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ToolError(f"file is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise ToolError(f"read failed: {exc}") from exc

        value: Any = data
        if field:
            for seg in field.split("."):
                value = self._step(value, seg)
        return {
            "path": path_arg,
            "field": field,
            "value": value,
            "type": type(value).__name__,
        }

    @staticmethod
    def _step(value: Any, seg: str) -> Any:
        if isinstance(value, list):
            try:
                idx = int(seg)
            except ValueError as exc:
                msg = f"path segment {seg!r} is not a valid array index"
                raise ToolError(msg) from exc
            try:
                return value[idx]
            except IndexError as exc:
                raise ToolError(f"index {idx} out of range") from exc
        if isinstance(value, dict):
            if seg not in value:
                raise ToolError(f"key {seg!r} not found")
            return value[seg]
        msg = f"cannot descend into {type(value).__name__} with segment {seg!r}"
        raise ToolError(msg)


@dataclass
class CurrentTimeTool:
    """Return the current UTC timestamp.

    LLMs hallucinate dates with abandon. This tool fixes that by
    grounding the agent in a real, machine-supplied timestamp.
    """

    name: str = "current_time"
    description: str = (
        "Return the current UTC time as ISO 8601 + a Unix epoch second. "
        "Use whenever the agent needs to know what 'now' is."
    )
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def call(self, args: Mapping[str, Any]) -> Any:
        del args
        now = datetime.now(timezone.utc)
        return {
            "iso": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "epoch_seconds": int(time.time()),
        }


def default_catalog(*, file_root: Path | None = None) -> tuple[Any, ...]:
    """Return the default credential-free MCP integration catalog.

    ``file_root`` defaults to the current working directory when
    ``None`` — appropriate for ``nom mcp-serve`` invoked from the
    user's project root. Production deployments override with the
    deployment's data directory.
    """
    root = (file_root or Path.cwd()).resolve()
    return (
        FileGlobTool(root=root),
        JSONFieldTool(root=root),
        CurrentTimeTool(),
    )
