"""Desktop app entry — pywebview window over an in-process FastAPI server.

The server runs in a daemon thread; the pywebview window owns the main
thread. On window close we ask uvicorn to exit cleanly, then join the
server thread.

This module avoids importing pywebview / uvicorn at module load so the
plain ``import nom.desktop`` from tests / introspection stays cheap.
The actual deps land in :func:`main`.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import closing
from typing import Any

DEFAULT_PORT = 8090
SERVER_READY_TIMEOUT_S = 30.0
SHUTDOWN_TIMEOUT_S = 5.0
WINDOW_TITLE = "Nôm"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 820
MIN_SIZE = (900, 640)


def _find_free_port(prefer: int = DEFAULT_PORT) -> int:
    """Return ``prefer`` if it is bindable on localhost, else any free port."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        try:
            probe.bind(("127.0.0.1", prefer))
            return prefer
        except OSError:
            pass
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as fallback:
        fallback.bind(("127.0.0.1", 0))
        return int(fallback.getsockname()[1])


def _wait_for_server(url: str, timeout: float = SERVER_READY_TIMEOUT_S) -> bool:
    """Poll ``url`` until any HTTP response or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0):
                return True
        except urllib.error.HTTPError:
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.2)
    return False


def _build_uvicorn_server(host: str, port: int, log_level: str) -> Any:
    """Build a ``uvicorn.Server`` bound to the in-process FastAPI app."""
    import uvicorn

    from nom.chat.server import build_app

    app = build_app()
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
    )
    return uvicorn.Server(config)


def _start_server_thread(server: Any) -> threading.Thread:
    thread = threading.Thread(target=server.run, name="nom-server", daemon=True)
    thread.start()
    return thread


def _shutdown_server(server: Any, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=SHUTDOWN_TIMEOUT_S)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nom-app",
        description="Nôm — Vietnamese AI desktop app.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("NOM_DESKTOP_PORT", DEFAULT_PORT)),
        help=f"Local server port. Default {DEFAULT_PORT} (falls back to a free port if taken).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host. Default 127.0.0.1 (localhost only — desktop apps should not expose LAN).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=os.environ.get("NOM_DESKTOP_DEBUG") == "1",
        help="Open the webview with developer tools enabled and verbose server logs.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
    )
    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_HEIGHT,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        import webview
    except ImportError:
        print(
            "nom-app requires pywebview. Install with: pip install nom-vn[desktop]",
            file=sys.stderr,
        )
        return 2

    port = _find_free_port(args.port)
    url = f"http://{args.host}:{port}"
    log_level = "info" if args.debug else "warning"

    print(f"starting embedded server on {url} ...", flush=True)
    server = _build_uvicorn_server(args.host, port, log_level)
    server_thread = _start_server_thread(server)

    if not _wait_for_server(url):
        print(
            f"server did not become ready within {SERVER_READY_TIMEOUT_S:.0f}s",
            file=sys.stderr,
        )
        _shutdown_server(server, server_thread)
        return 1

    webview.create_window(
        title=WINDOW_TITLE,
        url=url,
        width=args.width,
        height=args.height,
        min_size=MIN_SIZE,
    )
    try:
        webview.start(debug=args.debug)
    finally:
        _shutdown_server(server, server_thread)
    return 0


if __name__ == "__main__":
    sys.exit(main())
