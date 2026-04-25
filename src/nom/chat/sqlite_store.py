"""SQLite-backed Store — survives process restarts.

Layout under ``data_dir`` (default :class:`LocalDiskCache` placement)::

    <data_dir>/
        nom.db                  # SQLite — spaces, materials (BLOB), chunks
        embeddings/             # EmbeddingsCache directory
            <material_id>.npy   # one float32 matrix per indexed material

The RAG state for a space is rebuilt lazily on the first ``ask`` after
process start (or after ``add_material``):

- Materials with ``indexed=1`` reuse cached chunks (from SQL) and
  embeddings (from the injected :class:`EmbeddingsCache`). No
  re-embedding.
- Materials with ``indexed=0`` are parsed → chunked → embedded once,
  then their chunks + embedding matrix are written through the cache
  and the ``indexed`` flag is flipped. Subsequent restarts reuse the
  cache.

The vector storage is pluggable: pass any
:class:`nom.chat.embeddings_cache.EmbeddingsCache`. Default is
:class:`LocalDiskCache` at ``data_dir/embeddings/``. Future
``S3Cache`` / ``GcsCache`` / ``RedisCache`` slot in unchanged — see
``docs/architecture.md`` Layer 4.

Cold-start cost is dominated by cache reads + BM25 tokenization —
neither calls the embedder. The expensive embed-batch only runs for
newly added materials.

Shape matches :class:`nom.chat.store.Store` Protocol — pass either
``MemoryStore`` or ``SqliteStore`` to ``build_app(store=...)``.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from nom.chat.embeddings_cache import EmbeddingsCache, LocalDiskCache
from nom.chat.store import Material, Space

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from nom.embeddings import Embedder
    from nom.llm import LLM
    from nom.rag import Answer

__all__ = ["SqliteStore"]


_SCHEMA_VERSION = 1

# Cap the in-memory RAG cache so a long-running multi-space server
# doesn't grow unbounded. Each cached entry holds the full embeddings
# matrix + tokenized BM25 state for that space's chunks.
_DEFAULT_CACHE_MAX = 16

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS spaces (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS materials (
    id          TEXT PRIMARY KEY,
    space_id    TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    n_bytes     INTEGER NOT NULL,
    n_chunks    INTEGER NOT NULL DEFAULT 0,
    uploaded_at REAL NOT NULL,
    content     BLOB NOT NULL,
    indexed     INTEGER NOT NULL DEFAULT 0,
    position    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_materials_space ON materials(space_id, position);

CREATE TABLE IF NOT EXISTS chunks (
    material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    local_idx   INTEGER NOT NULL,
    text        TEXT NOT NULL,
    PRIMARY KEY (material_id, local_idx)
);
"""


@dataclass(slots=True)
class _IndexedSpace:
    """Cached RAG state for a space — discarded on add_material."""

    rag: Any  # nom.rag.RAG; Any to avoid eager numpy/torch import here


class SqliteStore:
    """Persistent store backed by SQLite + a pluggable EmbeddingsCache.

    Args:
        data_dir: directory to hold ``nom.db`` (and the default
            ``embeddings/`` cache directory if no ``embeddings_cache``
            is passed). Created with parents if absent.
        llm: any LLM-shaped object. Required.
        embedder: optional ``Embedder``. Defaults to
            ``VietnameseEmbedder`` (lazy-loaded only when needed).
        embeddings_cache: optional :class:`EmbeddingsCache`. Defaults
            to :class:`LocalDiskCache` rooted at ``data_dir/embeddings``.
            Pass a different impl (S3, GCS, Redis, in-memory) to swap
            backends without changing the rest of the layer.
        cache_max: maximum number of per-space RAG indexes held in
            memory. LRU-evicted past this. Default 16.

    The store is safe to share across threads of one process. Multiple
    processes pointed at the same ``data_dir`` will get SQLite-level
    locking but no in-memory cache coordination — single-process use is
    the supported pattern.
    """

    def __init__(
        self,
        data_dir: str | Path,
        *,
        llm: LLM,
        embedder: Embedder | None = None,
        embeddings_cache: EmbeddingsCache | None = None,
        cache_max: int = _DEFAULT_CACHE_MAX,
    ) -> None:
        if llm is None:
            raise ValueError("SqliteStore requires an `llm`.")
        self._data_dir = Path(data_dir).expanduser().resolve()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "nom.db"

        self._llm = llm
        self._embedder = embedder
        self._cache: EmbeddingsCache = embeddings_cache or LocalDiskCache(
            self._data_dir / "embeddings"
        )
        self._cache_max = max(1, cache_max)
        self._lock = threading.RLock()
        # Serializes _build_rag() across threads so two concurrent first-asks
        # of the same (or different) spaces don't both run expensive
        # parse+embed work. Reads of an already-cached RAG don't take this.
        self._build_lock = threading.Lock()
        self._rag_cache: OrderedDict[str, _IndexedSpace] = OrderedDict()

        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage txns explicitly
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)
        # Only write schema_version on first init — subsequent runs read it.
        if self._get_meta("schema_version") is None:
            self._set_meta("schema_version", str(_SCHEMA_VERSION))

    # ------------------------------------------------------------------
    # Meta helpers
    # ------------------------------------------------------------------

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def _get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _get_meta_int(self, key: str) -> int | None:
        raw = self._get_meta(key)
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Spaces
    # ------------------------------------------------------------------

    def list_spaces(self) -> list[Space]:
        """Return all spaces with their materials populated.

        Two SQL queries total (spaces + materials), regardless of how
        many spaces exist — avoids the N+1 fan-out of one query per
        space.
        """
        with self._lock:
            space_rows = self._conn.execute(
                "SELECT id, name, created_at FROM spaces ORDER BY created_at"
            ).fetchall()
            if not space_rows:
                return []
            mat_rows = self._conn.execute(
                "SELECT id, space_id, name, n_bytes, n_chunks, uploaded_at "
                "FROM materials ORDER BY space_id, position"
            ).fetchall()
        by_space: dict[str, list[Material]] = {}
        for row in mat_rows:
            by_space.setdefault(row[1], []).append(Material(*row))
        return [
            Space(id=sid, name=name, created_at=ca, materials=by_space.get(sid, []))
            for sid, name, ca in space_rows
        ]

    def create_space(self, name: str) -> Space:
        if not name.strip():
            raise ValueError("space name cannot be empty")
        with self._lock:
            sid = uuid.uuid4().hex[:12]
            now = time.time()
            self._conn.execute(
                "INSERT INTO spaces(id, name, created_at) VALUES(?, ?, ?)",
                (sid, name.strip(), now),
            )
            return Space(id=sid, name=name.strip(), created_at=now, materials=[])

    def get_space(self, space_id: str) -> Space | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, created_at FROM spaces WHERE id=?", (space_id,)
            ).fetchone()
            if row is None:
                return None
            sid, name, created_at = row
            return Space(
                id=sid,
                name=name,
                created_at=created_at,
                materials=self.list_materials(sid),
            )

    def delete_space(self, space_id: str) -> bool:
        with self._lock:
            mat_ids = [
                r[0]
                for r in self._conn.execute(
                    "SELECT id FROM materials WHERE space_id=?", (space_id,)
                ).fetchall()
            ]
            cur = self._conn.execute("DELETE FROM spaces WHERE id=?", (space_id,))
            if cur.rowcount == 0:
                return False
            for mid in mat_ids:
                self._cache.delete(mid)
            self._rag_cache.pop(space_id, None)
            return True

    # ------------------------------------------------------------------
    # Materials
    # ------------------------------------------------------------------

    def add_material(self, space_id: str, name: str, content: bytes) -> Material:
        with self._lock:
            if not self._space_exists(space_id):
                raise KeyError(f"unknown space: {space_id}")
            mid = uuid.uuid4().hex[:12]
            now = time.time()
            position = self._next_position(space_id)
            self._conn.execute(
                "INSERT INTO materials"
                "(id, space_id, name, n_bytes, n_chunks, uploaded_at, content, indexed, position)"
                " VALUES(?, ?, ?, ?, 0, ?, ?, 0, ?)",
                (mid, space_id, name, len(content), now, content, position),
            )
            self._rag_cache.pop(space_id, None)
            return Material(
                id=mid,
                space_id=space_id,
                name=name,
                n_bytes=len(content),
                n_chunks=0,
                uploaded_at=now,
            )

    def list_materials(self, space_id: str) -> list[Material]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, space_id, name, n_bytes, n_chunks, uploaded_at "
                "FROM materials WHERE space_id=? ORDER BY position",
                (space_id,),
            ).fetchall()
            return [Material(*r) for r in rows]

    def get_material_content(self, space_id: str, material_id: str) -> tuple[str, bytes] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT name, content FROM materials WHERE id=? AND space_id=?",
                (material_id, space_id),
            ).fetchone()
        if row is None:
            return None
        name, content = row
        # SQLite returns memoryview-like; coerce to bytes for the API surface.
        return name, bytes(content)

    def get_material_text(self, space_id: str, material_id: str) -> tuple[str, str] | None:
        result = self.get_material_pages(space_id, material_id)
        if result is None:
            return None
        name, pages = result
        return name, "\n\n".join(pages)

    def get_material_pages(self, space_id: str, material_id: str) -> tuple[str, list[str]] | None:
        """Return the raw Parse output — paragraphs / sheets / slides.

        Always re-parses (cheap for viewing, ~50ms for typical DOCX).
        Deliberately skips ``Normalize`` because that stage collapses
        internal whitespace — including the newlines that delimit a
        slide title from its body, or table rows from each other.
        Viewers want the structural shape. The Extracted tab uses
        :meth:`get_material_chunks` for the post-normalize / post-chunk
        text.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT name, content FROM materials WHERE id=? AND space_id=?",
                (material_id, space_id),
            ).fetchone()
        if row is None:
            return None
        name, content = row
        from nom.doc import OCR, Context, Load, Parse

        try:
            ctx = Context(source=bytes(content))
            Load().run(ctx)
            Parse().run(ctx)
            if ctx.needs_ocr:
                with contextlib.suppress(ImportError):
                    OCR().run(ctx)
            pages = ctx.pages_text or [ctx.text or ""]
        except Exception as exc:
            pages = [f"[parse error: {exc}]"]
        return name, pages

    def get_material_chunks(self, space_id: str, material_id: str) -> tuple[str, list[str]] | None:
        """Return the persisted chunks — what the chunker + embedder saw.

        Used by the viewer's "Extracted" tab. Empty list if not yet
        indexed.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT name FROM materials WHERE id=? AND space_id=?",
                (material_id, space_id),
            ).fetchone()
            if row is None:
                return None
            name = row[0]
            chunk_rows = self._conn.execute(
                "SELECT text FROM chunks WHERE material_id=? ORDER BY local_idx",
                (material_id,),
            ).fetchall()
        return name, [r[0] for r in chunk_rows]

    # ------------------------------------------------------------------
    # Q&A
    # ------------------------------------------------------------------

    def ask(self, space_id: str, question: str, *, top_k: int = 5) -> Answer:
        from nom.rag import Answer

        with self._lock:
            if not self._space_exists(space_id):
                raise KeyError(f"unknown space: {space_id}")
            has_material = (
                self._conn.execute(
                    "SELECT 1 FROM materials WHERE space_id=? LIMIT 1", (space_id,)
                ).fetchone()
                is not None
            )
            if not has_material:
                return Answer(
                    text="This space has no materials yet — upload some first.",
                    citations=[],
                    n_retrieved=0,
                )
            cached = self._cache_get(space_id)

        if cached is None:
            with self._build_lock:
                # Double-check inside build_lock — another thread may
                # have built and cached while we were waiting.
                with self._lock:
                    cached = self._cache_get(space_id)
                if cached is None:
                    rag = self._build_rag(space_id)
                    with self._lock:
                        self._cache_put(space_id, _IndexedSpace(rag=rag))
                    cached = _IndexedSpace(rag=rag)

        result: Answer = cached.rag.ask(question, top_k=top_k)
        return result

    def index_pending(self, space_id: str) -> int:
        """Eagerly process all unindexed materials in a space.

        Reuses ``_build_rag`` (the same path ``ask`` triggers lazily)
        but skips the LLM. Synchronous — caller is responsible for
        showing a loading state.
        """
        with self._lock:
            if not self._space_exists(space_id):
                raise KeyError(f"unknown space: {space_id}")
            n_pending = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM materials WHERE space_id=? AND indexed=0",
                    (space_id,),
                ).fetchone()[0]
            )
        if n_pending == 0:
            return 0
        with self._build_lock:
            rag = self._build_rag(space_id)
            with self._lock:
                self._cache_put(space_id, _IndexedSpace(rag=rag))
        return n_pending

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()
            self._rag_cache.clear()

    def __enter__(self) -> SqliteStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _cache_get(self, space_id: str) -> _IndexedSpace | None:
        entry = self._rag_cache.get(space_id)
        if entry is not None:
            self._rag_cache.move_to_end(space_id)
        return entry

    def _cache_put(self, space_id: str, entry: _IndexedSpace) -> None:
        self._rag_cache[space_id] = entry
        self._rag_cache.move_to_end(space_id)
        while len(self._rag_cache) > self._cache_max:
            self._rag_cache.popitem(last=False)

    def _space_exists(self, space_id: str) -> bool:
        return (
            self._conn.execute("SELECT 1 FROM spaces WHERE id=?", (space_id,)).fetchone()
            is not None
        )

    def _next_position(self, space_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM materials WHERE space_id=?",
            (space_id,),
        ).fetchone()
        return int(row[0])

    def _ensure_embedder(self) -> Embedder:
        if self._embedder is None:
            from nom.embeddings import VietnameseEmbedder

            self._embedder = VietnameseEmbedder()
        return self._embedder

    def _build_rag(self, space_id: str) -> Any:
        """Reconstruct the per-space RAG.

        For materials already indexed (``indexed=1``) chunks are loaded
        from SQL and embeddings from disk — no model call.

        For pending materials (``indexed=0``), we parse + chunk each
        first, then run **a single** ``embed_batch`` over the union of
        all pending chunks to amortize model overhead. After the call
        we split the resulting matrix back per-material and persist
        each atomically before flipping its ``indexed`` flag.
        """
        from nom.chunking import smart_chunk
        from nom.rag import RAG, source_to_text
        from nom.retrieve import BM25Retriever, DenseRetriever

        with self._lock:
            mats = self._conn.execute(
                "SELECT id, name, content, indexed FROM materials "
                "WHERE space_id=? ORDER BY position",
                (space_id,),
            ).fetchall()

        all_chunks: list[str] = []
        chunk_doc_idx: list[int] = []
        chunk_local_idx: list[int] = []
        embedding_blocks: list[NDArray[np.floating[Any]]] = []

        # Phase 1: load indexed materials (cheap — disk + SQL)
        loaded: dict[str, tuple[list[str], NDArray[np.floating[Any]]]] = {}
        for mid, _name, _content, indexed in mats:
            if indexed:
                loaded[mid] = self._load_indexed_material(mid)

        # Phase 2: parse + chunk pending materials, collect all texts
        pending: list[tuple[str, list[str]]] = []  # (material_id, chunk_texts)
        for mid, _name, content, indexed in mats:
            if indexed:
                continue
            chunk_texts = self._parse_and_chunk(content, source_to_text, smart_chunk)
            if not chunk_texts:
                with self._lock:
                    self._conn.execute(
                        "UPDATE materials SET indexed=1, n_chunks=0 WHERE id=?", (mid,)
                    )
                continue
            pending.append((mid, chunk_texts))

        # Phase 3: ONE embed_batch over all pending chunks, then split + persist
        if pending:
            flat_texts = [t for _mid, texts in pending for t in texts]
            embedder = self._ensure_embedder()
            flat_vecs = embedder.embed_batch(flat_texts).astype("float32", copy=False)
            self._validate_or_record_dim(int(flat_vecs.shape[1]), embedder)

            offset = 0
            for mid, texts in pending:
                n = len(texts)
                slice_vecs = flat_vecs[offset : offset + n]
                offset += n
                self._persist_indexed_material(mid, texts, slice_vecs)
                loaded[mid] = (texts, slice_vecs)

        # Assemble in original insertion order
        for di, (mid, _name, _content, _indexed) in enumerate(mats):
            entry = loaded.get(mid)
            if entry is None:
                continue
            texts, vecs = entry
            if not texts:
                continue
            for ci, t in enumerate(texts):
                all_chunks.append(t)
                chunk_doc_idx.append(di)
                chunk_local_idx.append(ci)
            embedding_blocks.append(vecs)

        if not all_chunks:
            return _EmptyRag(llm=self._llm, embedder=self._ensure_embedder())

        embeddings = np.vstack(embedding_blocks).astype("float32", copy=False)
        bm25 = BM25Retriever.fit(all_chunks)
        dense = DenseRetriever(embeddings, documents=all_chunks)

        return RAG(
            chunks_text=all_chunks,
            chunk_doc_idx=chunk_doc_idx,
            chunk_local_idx=chunk_local_idx,
            bm25=bm25,
            dense=dense,
            embedder=self._ensure_embedder(),
            llm=self._llm,
        )

    def _load_indexed_material(
        self, material_id: str
    ) -> tuple[list[str], NDArray[np.floating[Any]]]:
        """Load persisted chunks + embeddings for an already-indexed material."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT text FROM chunks WHERE material_id=? ORDER BY local_idx",
                (material_id,),
            ).fetchall()
        texts = [r[0] for r in rows]
        if not texts:
            return [], np.zeros((0, 0), dtype="float32")
        vecs = self._cache.get(material_id)
        if vecs is None:
            # Cache lost the entry but SQL still has the chunks — treat as drift.
            return [], np.zeros((0, 0), dtype="float32")
        if vecs.shape[0] != len(texts):
            # On-disk drift between chunks and embeddings — re-index.
            return [], np.zeros((0, 0), dtype="float32")
        # If the stored matrix is the wrong dim for the current embedder,
        # surface a clear error rather than letting np.vstack crash with
        # an opaque shape mismatch later.
        stored_dim = self._get_meta_int("embedder_dim")
        if stored_dim is not None and int(vecs.shape[1]) != stored_dim:
            raise ValueError(
                f"Cached embeddings for material {material_id} have dim "
                f"{vecs.shape[1]} but data dir was indexed at dim {stored_dim}. "
                "Restore the original embedder or wipe the data dir to re-index."
            )
        return texts, vecs

    def _parse_and_chunk(
        self,
        content: bytes,
        source_to_text: Any,
        smart_chunk: Any,
    ) -> list[str]:
        """Parse one material's bytes and return its chunk texts.

        Chunk size note: 256 word-tokens (not 512). Vietnamese word
        tokens explode 2-3x when re-tokenized by BPE / WordPiece — a
        512-word chunk becomes 1000+ subwords and overruns BGE-base's
        512-position embedding table. 256 leaves headroom for any
        embedder we ship.
        """
        text = source_to_text(content)
        if not text.strip():
            return []
        chunks = smart_chunk(text, max_tokens=256, overlap=48)
        return [c.text for c in chunks]

    def _persist_indexed_material(
        self,
        material_id: str,
        texts: list[str],
        vecs: NDArray[np.floating[Any]],
    ) -> None:
        """Write embeddings to disk + insert chunks + flip indexed flag.

        Crash-safety ordering: write the embedding cache first (the
        cache impl is responsible for its own atomicity — see
        :class:`LocalDiskCache.put`), then commit chunk rows +
        ``indexed=1`` in one SQL transaction. If we crash between,
        the orphan cache entry is harmless and gets overwritten on
        the next index attempt for this material id.
        """
        self._cache.put(material_id, vecs)
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.executemany(
                    "INSERT INTO chunks(material_id, local_idx, text) VALUES(?, ?, ?)",
                    [(material_id, i, t) for i, t in enumerate(texts)],
                )
                self._conn.execute(
                    "UPDATE materials SET indexed=1, n_chunks=? WHERE id=?",
                    (len(texts), material_id),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                self._cache.delete(material_id)
                raise

    def _validate_or_record_dim(self, dim: int, embedder: Embedder) -> None:
        """Lock in the embedder identity on first index; reject mismatches after.

        A data dir is bound to one embedder dim. If a user later swaps to
        an embedder with a different dim, the on-disk vectors and any new
        ones would be incompatible — mixing them would silently degrade
        retrieval. Refuse with a clear message instead.
        """
        stored = self._get_meta_int("embedder_dim")
        if stored is None:
            with self._lock:
                self._set_meta("embedder_name", str(getattr(embedder, "name", "unknown")))
                self._set_meta("embedder_dim", str(dim))
            return
        if stored != dim:
            stored_name = self._get_meta("embedder_name") or "unknown"
            current_name = str(getattr(embedder, "name", "unknown"))
            raise ValueError(
                f"Data dir was indexed with embedder {stored_name!r} (dim {stored}); "
                f"current embedder {current_name!r} produces dim {dim}. "
                "Either restore the original embedder or wipe the data dir to re-index."
            )


class _EmptyRag:
    """Stand-in returned when a space has materials but zero indexable chunks.

    All known materials parsed to empty text — keep ``ask`` returning a
    well-shaped Answer rather than raising.
    """

    def __init__(self, *, llm: LLM, embedder: Embedder) -> None:
        self.llm = llm
        self.embedder = embedder

    def ask(self, question: str, *, top_k: int | None = None) -> Answer:
        from nom.rag import Answer

        del question, top_k
        return Answer(
            text="No indexable text was extracted from the uploaded materials.",
            citations=[],
            n_retrieved=0,
        )
