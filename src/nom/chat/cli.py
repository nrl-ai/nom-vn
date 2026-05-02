"""CLI entry point — ``nom serve`` launches the FastAPI app.

Usage::

    nom serve                              # default model qwen3:8b on port 8080
    nom serve --port 9000
    nom serve --model llama3.1:8b
    nom serve --host 0.0.0.0               # listen on all interfaces
    nom serve --ollama-url http://gpu-box:11434
    nom serve --data-dir /var/lib/nom      # persistent storage location
    nom serve --in-memory                  # ephemeral (no disk persistence)

By default, spaces and indexed embeddings persist under ``~/.nom`` so a
restart reuses cached embeddings. Pass ``--in-memory`` for an ephemeral
session (useful for one-off demos).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any

__all__ = ["main", "serve"]


def _autodetect_tessdata_prefix() -> str | None:
    """Locate tesseract's tessdata directory and set TESSDATA_PREFIX if unset.

    Conda-installed tesseract puts ``tessdata/`` next to its ``bin/``
    (``…/share/tessdata`` from ``…/bin/tesseract``). System-installed
    tesseract is usually self-locating. If TESSDATA_PREFIX is already
    set we don't override.

    Returns the resolved path (or already-set value) for logging, or
    ``None`` if no tesseract / tessdata could be found.
    """
    if "TESSDATA_PREFIX" in os.environ:
        return os.environ["TESSDATA_PREFIX"]
    tesseract_bin = shutil.which("tesseract")
    if not tesseract_bin:
        return None
    bin_dir = Path(tesseract_bin).resolve().parent
    for candidate in (
        bin_dir.parent / "share" / "tessdata",
        bin_dir.parent / "share" / "tesseract-ocr" / "5" / "tessdata",
        bin_dir.parent / "share" / "tesseract-ocr" / "4.00" / "tessdata",
        Path("/usr/share/tesseract-ocr/5/tessdata"),
        Path("/usr/share/tessdata"),
    ):
        if (candidate / "vie.traineddata").is_file() or (candidate / "eng.traineddata").is_file():
            os.environ["TESSDATA_PREFIX"] = str(candidate)
            return str(candidate)
    return None


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    backend: str = "ollama",
    model: str | None = None,
    ollama_url: str = "http://localhost:11434",
    llamacpp_url: str = "http://127.0.0.1:8080/v1",
    embedder: Any | None = None,
    open_browser: bool = True,
    data_dir: str | Path | None = "~/.nom",
) -> None:
    """Start the Nôm chat server.

    Args:
        host: bind address. Default ``127.0.0.1`` (localhost only).
            Use ``0.0.0.0`` to allow LAN access.
        port: TCP port. Default ``8080``.
        backend: LLM backend. ``ollama`` (default), ``llamacpp``,
            ``openai``, or ``anthropic``. Override via ``NOM_LLM_BACKEND``.
        model: model id for the chosen backend. Default depends on
            backend: ``qwen3:8b`` (ollama), ``llamacpp`` (llamacpp,
            ignored by llama-server but recorded in logs),
            ``gpt-4o-mini`` (openai), ``claude-haiku-4-5`` (anthropic).
            Override via ``NOM_LLM_MODEL``.
        ollama_url: Ollama server URL (only used when backend=ollama).
        llamacpp_url: llama-server URL (only used when backend=llamacpp).
            Must include ``/v1``. Override via ``NOM_LLAMACPP_URL``.
        embedder: optional :class:`nom.embeddings.Embedder` instance.
            Defaults to ``VietnameseEmbedder`` (lazy-loaded).
        open_browser: if True, opens the default browser at the running URL.
        data_dir: directory for persistent storage (SQLite + cached
            embeddings). Default ``~/.nom``. Pass ``None`` for an
            ephemeral in-memory store.
    """
    try:
        import uvicorn
    except ImportError as exc:
        raise ImportError(
            "`nom serve` requires uvicorn. Install with: pip install nom-vn[chat]"
        ) from exc

    import os

    from nom.chat.server import build_app
    from nom.chat.sqlite_store import SqliteStore
    from nom.chat.store import MemoryStore

    backend = (os.environ.get("NOM_LLM_BACKEND") or backend).lower()
    model = os.environ.get("NOM_LLM_MODEL") or model

    if backend == "ollama":
        from nom.llm import Ollama

        llm: Any = Ollama(model=model or "qwen3:8b", base_url=ollama_url)
        backend_label = f"ollama({llm.model}) via {ollama_url}"
    elif backend == "llamacpp":
        from nom.llm import LlamaCpp

        llm = LlamaCpp(model=model or "llamacpp", base_url=llamacpp_url)
        backend_label = f"llamacpp({llm.model}) via {llamacpp_url}"
    elif backend in ("llamacpp-python", "llamacpp_python"):
        from nom.llm import LlamaCppPython

        if not model:
            raise SystemExit(
                "--backend llamacpp-python requires --model (a GGUF path or "
                "'hf:<repo>:<filename>' shorthand). Example: "
                "--model hf:bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"
            )
        llm = LlamaCppPython(model=model)
        backend_label = f"llamacpp-python({model})"
    elif backend in ("huggingface", "hf"):
        from nom.llm import HuggingFace

        llm = HuggingFace(model=model or "Qwen/Qwen2.5-3B-Instruct")
        backend_label = f"huggingface({llm.model_id})"
    elif backend == "openai":
        from nom.llm import OpenAI

        llm = OpenAI(model=model or "gpt-4o-mini")
        backend_label = f"openai({llm.model})"
    elif backend == "anthropic":
        from nom.llm import Anthropic

        llm = Anthropic(model=model or "claude-haiku-4-5-20251001")
        backend_label = f"anthropic({llm.model})"
    else:
        raise SystemExit(
            f"unknown LLM backend {backend!r}; expected "
            "ollama|llamacpp|llamacpp-python|huggingface|openai|anthropic"
        )

    if data_dir is None:
        store: Any = MemoryStore(embedder=embedder, llm=llm)
        store_label = "in-memory (ephemeral)"
    else:
        store = SqliteStore(data_dir, llm=llm, embedder=embedder)
        store_label = f"persistent at {Path(data_dir).expanduser()}"
    app = build_app(store=store)

    tessdata = _autodetect_tessdata_prefix()
    ocr_label = f"tesseract @ {tessdata}" if tessdata else "OCR disabled (tesseract not found)"

    url = f"http://{host}:{port}"
    print(f"Nôm — serving at {url}")
    print(f"  · llm:     {backend_label}")
    print(f"  · storage: {store_label}")
    print(f"  · ocr:     {ocr_label}")
    print(f"  · API docs at {url}/docs")

    if open_browser:
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:  # pragma: no cover - best effort
            pass

    uvicorn.run(app, host=host, port=port, log_level="info")


def main(argv: list[str] | None = None) -> int:
    """Top-level CLI dispatcher (``nom`` command)."""
    parser = argparse.ArgumentParser(
        prog="nom",
        description="Nôm — Vietnamese AI toolkit. Use `nom serve` to launch the web app.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="Launch the Nôm chat web app")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.add_argument(
        "--backend",
        default="ollama",
        choices=[
            "ollama",
            "llamacpp",
            "llamacpp-python",
            "huggingface",
            "openai",
            "anthropic",
        ],
        help="LLM backend (env: NOM_LLM_BACKEND). Default: ollama.",
    )
    p_serve.add_argument(
        "--model",
        default=None,
        help="Model id (env: NOM_LLM_MODEL). Default per backend: "
        "qwen3:8b / llamacpp / gpt-4o-mini / claude-haiku-4-5-20251001.",
    )
    p_serve.add_argument("--ollama-url", default="http://localhost:11434")
    p_serve.add_argument(
        "--llamacpp-url",
        default="http://127.0.0.1:8080/v1",
        help="llama-server URL incl. /v1 (env: NOM_LLAMACPP_URL).",
    )
    p_serve.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open the default browser",
    )
    storage = p_serve.add_mutually_exclusive_group()
    storage.add_argument(
        "--data-dir",
        default="~/.nom",
        help="Directory for persistent storage (default: ~/.nom)",
    )
    storage.add_argument(
        "--in-memory",
        action="store_true",
        help="Run with an ephemeral in-memory store (no disk persistence)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "serve":
        serve(
            host=args.host,
            port=args.port,
            backend=args.backend,
            model=args.model,
            ollama_url=args.ollama_url,
            llamacpp_url=args.llamacpp_url,
            open_browser=not args.no_browser,
            data_dir=None if args.in_memory else args.data_dir,
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
