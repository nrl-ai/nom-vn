"""Deployable chat-over-VN-docs web app.

Ships inside the Python package; one CLI command launches it::

    pip install "nom-vn[chat]"
    nom serve

This opens an HTTP server (FastAPI) at http://localhost:8080 with:

- A minimal vanilla-HTML UI for create-space / upload-material / ask.
- A REST + JSON API at ``/api/spaces``, ``/api/spaces/{id}/materials``,
  and ``/api/spaces/{id}/ask`` so external clients can drive the app.

Storage:

- :class:`Store` — in-memory (process-lifetime). Used for tests and
  ephemeral runs. Restart loses state.
- :class:`SqliteStore` — persistent: SQLite for metadata + raw bytes,
  one ``.npy`` per material for cached embeddings. ``nom serve`` uses
  this by default, rooted at ``~/.nom``. Cold-start RAG rebuild is
  load-from-disk only — no re-embedding.

The React + ShadCN UI (committed pre-built dist) lands in a later v0.2.x
patch; the swap from the bundled HTML to a ``StaticFiles`` mount over
``dist/`` is a one-line change.

OSS prior art / SOTA we lean on (April 2026):

- **FastAPI** (MIT) — mature Python web framework with native OpenAPI.
- **Pydantic v2** (already a hard dep) — request/response validation.
- **Vite + React + ShadCN/ui** (planned v0.2.1) — embed the built
  ``dist/`` via FastAPI ``StaticFiles``. Pattern documented in 2026
  by the FastAPI-React community for shipping an SPA inside a Python
  wheel: build at release time, ``hatch`` includes the ``dist/`` in
  the wheel, ``StaticFiles`` mounts it at runtime.
"""

from nom.chat.cli import serve
from nom.chat.embeddings_cache import EmbeddingsCache, LocalDiskCache, MemoryCache
from nom.chat.server import build_app
from nom.chat.sqlite_store import SqliteStore
from nom.chat.store import Material, MemoryStore, Space, Store

__all__ = [
    "EmbeddingsCache",
    "LocalDiskCache",
    "Material",
    "MemoryCache",
    "MemoryStore",
    "Space",
    "SqliteStore",
    "Store",
    "build_app",
    "serve",
]
