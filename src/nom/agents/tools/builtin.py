"""Built-in tools — the common starter set for any ``nom.agents`` deployment.

Every built-in here is intentionally simple:

- One Python class.
- Strict args validation in ``call``.
- Raises :class:`nom.agents.ToolError` on recoverable failures so the
  agent loop can retry; lets unexpected exceptions propagate.
- No hidden state — re-entrant.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nom.agents.protocol import ToolError

__all__ = [
    "FileReadTool",
    "HTTPGetTool",
    "PythonEvalTool",
    "RAGTool",
]


@dataclass
class RAGTool:
    """Search a ``nom.rag.RAG`` index and return an answer with citations.

    The first thing every "answer questions about my documents" agent
    reaches for. Wraps :meth:`nom.rag.RAG.ask`.
    """

    rag: Any
    name: str = "search_documents"
    description: str = (
        "Search the indexed Vietnamese documents and return an answer "
        "with citation snippets. Use whenever a question requires "
        "factual information from the document corpus."
    )
    schema: Mapping[str, Any] | None = None
    max_citations: int = 4

    def __post_init__(self) -> None:
        if self.schema is None:
            self.schema = {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to search for."},
                    "top_k": {
                        "type": "integer",
                        "description": "How many chunks to retrieve. Default 5.",
                    },
                },
                "required": ["question"],
            }

    def call(self, args: Mapping[str, Any]) -> Any:
        question = args.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ToolError("`question` is required and must be a non-empty string")
        top_k = int(args.get("top_k") or 5)
        try:
            answer = self.rag.ask(question, top_k=top_k)
        except TypeError:
            # Older RAG signatures don't accept top_k kw.
            answer = self.rag.ask(question)
        cites = getattr(answer, "citations", None) or []
        cite_lines = []
        for i, c in enumerate(cites[: self.max_citations]):
            text = getattr(c, "text", str(c))
            cite_lines.append(f"[{i + 1}] {text[:240]}")
        return {
            "answer": getattr(answer, "text", str(answer)),
            "citations": cite_lines,
            "n_retrieved": getattr(answer, "n_retrieved", len(cite_lines)),
        }


@dataclass
class HTTPGetTool:
    """Fetch a URL via HTTP GET. Domain allow-list enforced.

    Production deployments restrict ``allowed_hosts`` to internal
    services; never expose this with the default empty list (which
    blocks everything) without configuring it.
    """

    allowed_hosts: tuple[str, ...] = ()
    timeout_seconds: float = 5.0
    max_bytes: int = 200_000
    name: str = "http_get"
    description: str = (
        "Fetch a URL via HTTP GET and return the response body (truncated). "
        "Only URLs whose host is in the configured allow-list are permitted."
    )
    schema: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.schema is None:
            self.schema = {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full https:// URL."},
                },
                "required": ["url"],
            }

    def call(self, args: Mapping[str, Any]) -> Any:
        url = args.get("url")
        if not isinstance(url, str) or not url:
            raise ToolError("`url` is required")
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ToolError(f"unsupported scheme {parsed.scheme!r}; only http/https")
        if not self.allowed_hosts or parsed.hostname not in self.allowed_hosts:
            raise ToolError(
                f"host {parsed.hostname!r} not in allow-list {list(self.allowed_hosts)}"
            )

        try:
            import httpx
        except ImportError as exc:
            raise ToolError("httpx is required for HTTPGetTool") from exc

        try:
            r = httpx.get(url, timeout=self.timeout_seconds, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise ToolError(f"http error: {exc}") from exc
        body = r.text
        if len(body) > self.max_bytes:
            body = body[: self.max_bytes] + "…[truncated]"
        return {
            "status": r.status_code,
            "headers": dict(r.headers),
            "body": body,
        }


_SAFE_EXPR = re.compile(r"^[\d\s+\-*/().,%eE]+$")


@dataclass
class PythonEvalTool:
    """Evaluate a numeric Python expression. NO function calls or names.

    Strictly arithmetic — purposely minimal. For full code-as-action
    you want a sandboxed runner (E2B, Modal) wired separately; this
    tool covers the common "agent needs to do arithmetic mid-flow"
    use case without opening an exec hole.
    """

    name: str = "python_eval"
    description: str = (
        "Evaluate a numeric Python expression. Only arithmetic operators "
        "(+ - * / % parentheses) and numbers are allowed. Use for "
        "calculations the model shouldn't do in its head."
    )
    schema: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.schema is None:
            self.schema = {
                "type": "object",
                "properties": {
                    "expr": {
                        "type": "string",
                        "description": ("Arithmetic expression. Example: '(120 * 1.1 + 50) / 3'."),
                    },
                },
                "required": ["expr"],
            }

    def call(self, args: Mapping[str, Any]) -> Any:
        expr = args.get("expr")
        if not isinstance(expr, str):
            raise ToolError("`expr` is required and must be a string")
        if not _SAFE_EXPR.match(expr):
            raise ToolError(
                "expression contains disallowed characters; only digits and "
                "+ - * / % ( ) . , space are permitted"
            )
        try:
            value = eval(expr, {"__builtins__": {}}, {})
        except (SyntaxError, ValueError, ArithmeticError) as exc:
            raise ToolError(f"eval failed: {exc}") from exc
        return {"value": value}


@dataclass
class FileReadTool:
    """Read a file inside an allowed root.

    Path traversal blocked: the resolved path must be under
    ``root``. Symlinks are resolved before the check. Use for
    "answer questions about my project" agents that need to inspect
    code or data files alongside RAG search.
    """

    root: Path
    max_bytes: int = 200_000
    name: str = "file_read"
    description: str = (
        "Read a file by path (relative to the configured root). Returns "
        "the contents up to a size cap. Use for inspecting source code, "
        "configs, or data files the agent needs to read directly."
    )
    schema: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        if self.schema is None:
            self.schema = {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the agent's root directory.",
                    }
                },
                "required": ["path"],
            }

    def call(self, args: Mapping[str, Any]) -> Any:
        path_arg = args.get("path")
        if not isinstance(path_arg, str) or not path_arg:
            raise ToolError("`path` is required")
        candidate = (self.root / path_arg).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ToolError(f"path escapes root: {path_arg!r}") from exc
        if not candidate.exists():
            raise ToolError(f"file not found: {path_arg!r}")
        if not candidate.is_file():
            raise ToolError(f"not a regular file: {path_arg!r}")
        try:
            data = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ToolError(f"read failed: {exc}") from exc
        truncated = len(data) > self.max_bytes
        if truncated:
            data = data[: self.max_bytes]
        return {
            "path": str(candidate.relative_to(self.root)),
            "content": data,
            "truncated": truncated,
            "size": candidate.stat().st_size,
        }
