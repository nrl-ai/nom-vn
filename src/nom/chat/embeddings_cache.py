"""Embeddings cache — pluggable storage for per-material vector matrices.

The embed step is by far the most expensive part of building a RAG
index (seconds-to-minutes per material on CPU). Caching its output is
the single biggest performance lever in the persistence layer.

This module isolates that cache behind a Protocol so the swap path is:

- **Local single-user**: ``LocalDiskCache`` — one ``.npy`` per
  material id under a directory. (Default for ``SqliteStore``.)
- **Cloud multi-pod** (planned): ``S3Cache`` / ``GcsCache`` — same
  Protocol, blob-storage backend. App code doesn't change.
- **Tests / ephemeral** : ``MemoryCache`` — keeps matrices in a dict.

Why a Protocol and not just a function-pair? Because the *failure
modes* differ across backends (network timeouts, eventual consistency,
permission errors) and isolating them behind a single interface keeps
the calling code in :class:`nom.chat.SqliteStore` linear and readable.

See ``docs/architecture.md`` Layer 4 for where this fits.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["EmbeddingsCache", "LocalDiskCache", "MemoryCache"]


@runtime_checkable
class EmbeddingsCache(Protocol):
    """Per-material embedding-matrix cache shape.

    Each material is keyed by a stable id (typically the material's
    primary key in the surrounding ``Store``). Matrices are 2-D
    float32 numpy arrays of shape ``(n_chunks, dim)`` and are
    expected to be **L2-normalized** by the caller (the contract every
    ``nom.embeddings.Embedder`` already promises).

    Implementations MUST be:
    - **Atomic on put** — a partial write must not leave a corrupt
      readable state.
    - **Idempotent on delete** — deleting a missing key is not an
      error.
    - **Safe under concurrent reads** of the same key.
    """

    def put(self, key: str, vecs: NDArray[np.floating[Any]]) -> None: ...
    def get(self, key: str) -> NDArray[np.floating[Any]] | None: ...
    def delete(self, key: str) -> None: ...
    def has(self, key: str) -> bool: ...


class LocalDiskCache:
    """One ``.npy`` per key under a directory. The default cache for
    :class:`nom.chat.SqliteStore`.

    Atomic writes via temp-file + ``rename()`` — survives mid-write
    crashes (partial files left behind get overwritten on retry).

    Args:
        directory: filesystem path. Created (with parents) if absent.
    """

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory).expanduser().resolve()
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def directory(self) -> Path:
        return self._dir

    def _path(self, key: str) -> Path:
        # Keys are typically uuid hex (12 char), already filesystem-safe.
        # We don't validate; corruption-via-bad-key is caller's bug.
        return self._dir / f"{key}.npy"

    def put(self, key: str, vecs: NDArray[np.floating[Any]]) -> None:
        path = self._path(key)
        tmp = path.with_name(path.name + ".tmp")
        # np.save would append ".npy" to a path argument unless it
        # already ends with .npy — using an open file handle keeps the
        # exact suffix we picked.
        with tmp.open("wb") as fh:
            np.save(fh, vecs, allow_pickle=False)
        tmp.replace(path)

    def get(self, key: str) -> NDArray[np.floating[Any]] | None:
        path = self._path(key)
        if not path.is_file():
            return None
        loaded: NDArray[np.floating[Any]] = np.load(path, allow_pickle=False)
        return loaded

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def has(self, key: str) -> bool:
        return self._path(key).is_file()


class MemoryCache:
    """In-process dict cache. For tests and ephemeral runs.

    No persistence — losing the process loses the cache. Use this when
    speed of bring-up matters more than reload cost.
    """

    def __init__(self) -> None:
        self._d: dict[str, NDArray[np.floating[Any]]] = {}

    def put(self, key: str, vecs: NDArray[np.floating[Any]]) -> None:
        self._d[key] = vecs.copy()  # defensive — caller may mutate later

    def get(self, key: str) -> NDArray[np.floating[Any]] | None:
        return self._d.get(key)

    def delete(self, key: str) -> None:
        self._d.pop(key, None)

    def has(self, key: str) -> bool:
        return key in self._d
