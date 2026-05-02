"""Desktop app shell — pywebview window over the embedded FastAPI server.

Runs ``nom serve`` in-process on a free local port and renders it in a
pywebview window backed by the OS native webview (WKWebView on macOS,
WebView2 on Windows, WebKitGTK on Linux). Designed to be packaged as a
single binary via PyInstaller (``desktop/nom-app.spec``).

Entry point: ``nom-app`` console script → :func:`nom.desktop.main.main`.

See ``desktop/README.md`` for build, dev hot-reload, and packaging
instructions.
"""

from nom.desktop.main import main

__all__ = ["main"]
