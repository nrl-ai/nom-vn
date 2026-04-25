"""Storage layer for the chat web app — Protocol + in-memory impl.

This module defines:

- :class:`Store` — a ``runtime_checkable`` :class:`typing.Protocol`
  for spaces, materials, and per-space RAG indexes. Anything with the
  shape of these methods conforms; no inheritance required.
- :class:`MemoryStore` — the in-process implementation. Restart loses
  everything. Used for tests and ephemeral runs (``nom serve --in-memory``).

The persistent counterpart lives in :class:`nom.chat.sqlite_store.SqliteStore`
and conforms to the same Protocol. ``nom serve`` defaults to ``SqliteStore``;
either may be passed to ``build_app(store=...)``.

The Protocol is the swap point. Future ``PostgresStore`` /
``MongoStore`` implementations only have to match these seven methods
— see ``docs/architecture.md`` Layer 4.
"""

from __future__ import annotations

import contextlib
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from nom.embeddings import Embedder
    from nom.llm import LLM
    from nom.rag import Answer

__all__ = ["Material", "MemoryStore", "Space", "Store"]


@dataclass(slots=True)
class Material:
    """A document/material uploaded to a space."""

    id: str
    space_id: str
    name: str
    n_bytes: int
    n_chunks: int  # 0 until indexed
    uploaded_at: float


@dataclass(slots=True)
class Space:
    """A named container of materials with its own RAG index."""

    id: str
    name: str
    created_at: float
    materials: list[Material] = field(default_factory=list)


@runtime_checkable
class Store(Protocol):
    """Storage shape any concrete store must satisfy.

    Marked ``runtime_checkable`` so ``isinstance(store, Store)`` works
    in tests and at boot — useful for picking up shape regressions
    when adding new implementations.

    Concrete implementations should be:
    - **Thread-safe within one process.** FastAPI workers will hit
      these methods concurrently. Coarse locking is fine at our scale.
    - **Lazy on indexing.** ``add_material`` should not block on
      embedding work; defer the heavy lift to the next ``ask`` call.

    For the durability and consistency contract on each method see
    the implementation docstrings.
    """

    def list_spaces(self) -> list[Space]: ...
    def create_space(self, name: str) -> Space: ...
    def get_space(self, space_id: str) -> Space | None: ...
    def delete_space(self, space_id: str) -> bool: ...
    def add_material(self, space_id: str, name: str, content: bytes) -> Material: ...
    def list_materials(self, space_id: str) -> list[Material]: ...
    def ask(self, space_id: str, question: str, *, top_k: int = 5) -> Answer: ...
    def get_material_content(self, space_id: str, material_id: str) -> tuple[str, bytes] | None:
        """Return ``(name, raw_bytes)`` of the material, or None if missing."""
        ...

    def get_material_text(self, space_id: str, material_id: str) -> tuple[str, str] | None:
        """Return ``(name, extracted_plain_text)``. Empty string if not yet indexed."""
        ...

    def get_material_pages(self, space_id: str, material_id: str) -> tuple[str, list[str]] | None:
        """Return ``(name, pages)`` — the structured per-page output of
        ``nom.doc.Parse``. Page semantics depend on format: PDFs are
        physical pages, DOCX is paragraphs + table rows, XLSX is sheets,
        PPTX is slides, others are a single-element list. Used by the
        browser viewer to render structured previews."""
        ...

    def get_material_chunks(self, space_id: str, material_id: str) -> tuple[str, list[str]] | None:
        """Return ``(name, chunks)`` — the persisted chunks (what the
        chunker + embedder saw). Empty list if not yet indexed. The
        viewer uses this for its "Extracted" tab."""
        ...

    def index_pending(self, space_id: str) -> int:
        """Process all materials with ``indexed=0`` (parse, chunk, embed,
        persist). Synchronous. No LLM call. Returns number of materials
        that were newly indexed (zero if everything was already up to
        date or the space is empty)."""
        ...


class MemoryStore:
    """In-memory storage for spaces, materials, and RAG indexes.

    Methods are thread-safe under a single ``RLock`` so concurrent
    FastAPI requests can mutate without races. Locking is coarse —
    fine for the single-user / dozens-of-spaces scale.
    """

    def __init__(self, *, embedder: Embedder | None = None, llm: LLM) -> None:
        if llm is None:
            raise ValueError("MemoryStore requires an `llm` (use any nom.llm.LLM-shaped object).")
        self._embedder = embedder
        self._llm = llm
        self._lock = threading.RLock()
        self._spaces: dict[str, Space] = {}
        # raw material bytes keyed by material id (for re-ingestion on update)
        self._material_bytes: dict[str, bytes] = {}
        # one RAG instance per space; None until at least one material is indexed
        self._rags: dict[str, Any] = {}  # space_id -> RAG | None

    # ------------------------------------------------------------------
    # Spaces
    # ------------------------------------------------------------------

    def list_spaces(self) -> list[Space]:
        with self._lock:
            return list(self._spaces.values())

    def create_space(self, name: str) -> Space:
        if not name.strip():
            raise ValueError("space name cannot be empty")
        with self._lock:
            sid = uuid.uuid4().hex[:12]
            space = Space(id=sid, name=name.strip(), created_at=time.time())
            self._spaces[sid] = space
            self._rags[sid] = None
            return space

    def get_space(self, space_id: str) -> Space | None:
        with self._lock:
            return self._spaces.get(space_id)

    def delete_space(self, space_id: str) -> bool:
        with self._lock:
            if space_id not in self._spaces:
                return False
            for m in self._spaces[space_id].materials:
                self._material_bytes.pop(m.id, None)
            del self._spaces[space_id]
            self._rags.pop(space_id, None)
            return True

    # ------------------------------------------------------------------
    # Materials
    # ------------------------------------------------------------------

    def add_material(self, space_id: str, name: str, content: bytes) -> Material:
        with self._lock:
            space = self._spaces.get(space_id)
            if space is None:
                raise KeyError(f"unknown space: {space_id}")
            mid = uuid.uuid4().hex[:12]
            mat = Material(
                id=mid,
                space_id=space_id,
                name=name,
                n_bytes=len(content),
                n_chunks=0,  # filled in by reindex
                uploaded_at=time.time(),
            )
            space.materials.append(mat)
            self._material_bytes[mid] = content
            # Mark the space's RAG as stale; re-indexed lazily on next ask
            self._rags[space_id] = None
            return mat

    def list_materials(self, space_id: str) -> list[Material]:
        with self._lock:
            space = self._spaces.get(space_id)
            return list(space.materials) if space else []

    def get_material_content(self, space_id: str, material_id: str) -> tuple[str, bytes] | None:
        with self._lock:
            space = self._spaces.get(space_id)
            if space is None:
                return None
            mat = next((m for m in space.materials if m.id == material_id), None)
            if mat is None:
                return None
            blob = self._material_bytes.get(material_id)
            if blob is None:
                return None
            return mat.name, blob

    def get_material_text(self, space_id: str, material_id: str) -> tuple[str, str] | None:
        result = self.get_material_pages(space_id, material_id)
        if result is None:
            return None
        name, pages = result
        return name, "\n\n".join(pages)

    def get_material_pages(self, space_id: str, material_id: str) -> tuple[str, list[str]] | None:
        """Re-parse on demand. Skip Normalize so structural newlines (PPTX
        slide title/body, DOCX paragraph breaks, XLSX rows) survive for
        the viewer. The chunker runs Normalize separately for the
        embedding path."""
        with self._lock:
            space = self._spaces.get(space_id)
            if space is None:
                return None
            mat = next((m for m in space.materials if m.id == material_id), None)
            if mat is None:
                return None
            blob = self._material_bytes.get(material_id)
            if blob is None:
                return mat.name, []
        from nom.doc import OCR, Context, Load, Parse

        try:
            ctx = Context(source=blob)
            Load().run(ctx)
            Parse().run(ctx)
            if ctx.needs_ocr:
                with contextlib.suppress(ImportError):
                    OCR().run(ctx)
            pages = ctx.pages_text or [ctx.text or ""]
        except Exception as exc:
            pages = [f"[parse error: {exc}]"]
        return mat.name, pages

    def get_material_chunks(self, space_id: str, material_id: str) -> tuple[str, list[str]] | None:
        """Pull chunks out of the cached RAG, if any. MemoryStore doesn't
        persist chunks separately so a fresh / never-asked space returns
        an empty list — the viewer's Extracted tab then shows the
        re-parsed pages instead.
        """
        with self._lock:
            space = self._spaces.get(space_id)
            if space is None:
                return None
            mat = next((m for m in space.materials if m.id == material_id), None)
            if mat is None:
                return None
            rag = self._rags.get(space_id)
            if rag is None:
                return mat.name, []
            # Find the doc index for this material — order of materials
            # is preserved when feeding RAG.from_documents in _build_rag.
            doc_idx = next(
                (i for i, m in enumerate(space.materials) if m.id == material_id),
                None,
            )
            if doc_idx is None:
                return mat.name, []
            chunks = [rag.chunks_text[i] for i, di in enumerate(rag.chunk_doc_idx) if di == doc_idx]
            return mat.name, chunks

    # ------------------------------------------------------------------
    # Q&A
    # ------------------------------------------------------------------

    def ask(self, space_id: str, question: str, *, top_k: int = 5) -> Answer:
        from nom.rag import Answer  # local import to avoid eager numpy load

        with self._lock:
            space = self._spaces.get(space_id)
            if space is None:
                raise KeyError(f"unknown space: {space_id}")
            if not space.materials:
                return Answer(
                    text="This space has no materials yet — upload some first.",
                    citations=[],
                    n_retrieved=0,
                )
            rag = self._rags.get(space_id)

        if rag is None:
            rag = self._build_rag(space_id)
            with self._lock:
                self._rags[space_id] = rag

        result: Answer = rag.ask(question, top_k=top_k)
        return result

    def index_pending(self, space_id: str) -> int:
        with self._lock:
            space = self._spaces.get(space_id)
            if space is None:
                raise KeyError(f"unknown space: {space_id}")
            n_pending = sum(1 for m in space.materials if m.n_chunks == 0)
            cached = self._rags.get(space_id) is not None
        if n_pending == 0 and cached:
            return 0
        # _build_rag does the parse + embed + chunk-count update for all
        # materials. For MemoryStore that means re-parsing everything,
        # but it's the existing path; specializing would duplicate logic.
        rag = self._build_rag(space_id)
        with self._lock:
            self._rags[space_id] = rag
        return n_pending

    def _build_rag(self, space_id: str) -> Any:
        """Construct a RAG over the current materials of a space.

        Released the lock during the heavy-lift (parse + embed + index)
        because that can take seconds and shouldn't block other API
        requests on unrelated spaces.
        """
        from nom.rag import RAG

        with self._lock:
            space = self._spaces[space_id]
            sources_and_names: list[tuple[bytes, str]] = []
            for m in space.materials:
                blob = self._material_bytes.get(m.id)
                if blob is not None:
                    sources_and_names.append((blob, m.name))

        sources: list[str | Path | bytes] = [b for b, _name in sources_and_names]
        rag = RAG.from_documents(sources, llm=self._llm, embedder=self._embedder)

        # Update each material's chunk count for UI display.
        with self._lock:
            counts = _materials_chunk_breakdown(rag, len(sources))
            for i, m in enumerate(self._spaces[space_id].materials):
                m.n_chunks = counts.get(i, 0)

        return rag


def _materials_chunk_breakdown(rag: Any, n_sources: int) -> dict[int, int]:
    """Count chunks attributed to each source-doc index in a RAG."""
    counts: dict[int, int] = dict.fromkeys(range(n_sources), 0)
    for di in rag.chunk_doc_idx:
        counts[di] = counts.get(di, 0) + 1
    return counts
