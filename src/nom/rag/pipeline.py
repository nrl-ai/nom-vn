"""RAG facade over the v0.0.x toolkit.

Design goals:

- **3-line happy path.** ``RAG.from_documents([...], llm=...)`` →
  ``rag.ask("...")`` → done. No intermediate object juggling.
- **Sensible defaults.** Everything optional has a default that works
  without arguments. Power users override what they need.
- **Protocol seams.** Every collaborator is a Protocol; swap any one
  without forking us.
- **Honest about state.** Construction does work (chunks, embeds,
  builds indexes). We don't pretend it's free.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from nom.chunking import smart_chunk
from nom.retrieve import BM25Retriever, DenseRetriever, hybrid_score

if TYPE_CHECKING:
    from nom.embeddings import Embedder
    from nom.llm import LLM


__all__ = ["RAG", "Answer", "Citation"]


@dataclass(frozen=True, slots=True)
class Citation:
    """Where in the indexed corpus this chunk came from.

    Attributes:
        doc_idx: index into the documents list passed to ``from_documents``.
        chunk_idx: position of the chunk within that document (0-based).
        score: hybrid retrieval score for this chunk against the question.
        text: the chunk's text content (handy for inline display).
    """

    doc_idx: int
    chunk_idx: int
    score: float
    text: str


@dataclass(frozen=True, slots=True)
class Answer:
    """Result of a single :meth:`RAG.ask` call.

    Attributes:
        text: the LLM's natural-language answer.
        citations: chunks the answer was grounded in, sorted by descending
            score. Length up to ``top_k`` (default 5).
        n_retrieved: how many chunks the retriever surfaced before the
            LLM was prompted (typically more than ``len(citations)``).
    """

    text: str
    citations: list[Citation]
    n_retrieved: int


@dataclass
class RAG:
    """High-level RAG pipeline. Construct via :meth:`from_documents`.

    Holds: chunked documents, BM25 + Dense indexes, embedder, LLM.
    Use :meth:`ask` for questions.

    Most users construct via the factory:

        >>> from nom.rag import RAG
        >>> from nom.llm import Ollama
        >>> rag = RAG.from_documents(
        ...     ["contract.pdf", "Plain text content also OK"],
        ...     llm=Ollama(model="qwen3:8b"),
        ... )
        >>> answer = rag.ask("What's the contract value?")
    """

    # Retrieval state — populated in from_documents()
    chunks_text: list[str]  # flat chunk index -> text
    chunk_doc_idx: list[int]  # flat chunk index -> source doc index
    chunk_local_idx: list[int]  # flat chunk index -> chunk-within-doc
    bm25: BM25Retriever
    dense: DenseRetriever
    embedder: Embedder
    llm: LLM
    # Tunables
    top_k: int = 5
    n_retrieve: int = 20  # retrieve more, rerank-by-LLM via prompt
    rrf_k: int = 60
    name: str = field(default="rag", init=False)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_documents(
        cls,
        sources: list[str | Path | bytes],
        *,
        llm: LLM,
        embedder: Embedder | None = None,
        chunk_max_tokens: int = 512,
        chunk_overlap: int = 64,
        top_k: int = 5,
        n_retrieve: int = 20,
    ) -> RAG:
        """Build a RAG pipeline from a list of document sources.

        Each source can be:
        - A path to a PDF / image / text file (parsed via ``nom.doc.Pipeline``)
        - Raw bytes (same — magic-byte format detection)
        - A plain Python string (treated as text directly, no parse needed)

        Args:
            sources: list of mixed paths/bytes/strings.
            llm: an :class:`nom.llm.LLM` adapter (Ollama recommended for
                local; OpenAI/Anthropic when wired up in v0.1.1).
            embedder: optional :class:`nom.embeddings.Embedder`. Defaults
                to :class:`nom.embeddings.VietnameseEmbedder` (lazy-loaded).
            chunk_max_tokens: target chunk size in tokens. Default 512.
            chunk_overlap: token overlap between chunks. Default 64.
            top_k: how many cited chunks to include with each answer.
                Default 5.
            n_retrieve: how many chunks to retrieve before the LLM picks
                from them. Default 20.

        Returns:
            A ready-to-query :class:`RAG` instance.
        """
        if not sources:
            raise ValueError("RAG.from_documents requires at least one source")

        # 1. Parse each source into clean text
        doc_texts = [_source_to_text(s) for s in sources]

        # 2. Chunk each document
        all_chunks: list[str] = []
        chunk_doc_idx: list[int] = []
        chunk_local_idx: list[int] = []
        for di, text in enumerate(doc_texts):
            if not text.strip():
                continue
            doc_chunks = smart_chunk(
                text,
                max_tokens=chunk_max_tokens,
                overlap=chunk_overlap,
            )
            for ci, ch in enumerate(doc_chunks):
                all_chunks.append(ch.text)
                chunk_doc_idx.append(di)
                chunk_local_idx.append(ci)

        if not all_chunks:
            raise ValueError("RAG.from_documents produced no chunks (all sources empty?)")

        # 3. Lazy default embedder
        active_embedder: Embedder
        if embedder is None:
            from nom.embeddings import VietnameseEmbedder

            active_embedder = VietnameseEmbedder()
        else:
            active_embedder = embedder

        # 4. Embed all chunks (single batch)
        embeddings = active_embedder.embed_batch(all_chunks)

        # 5. Build BM25 + Dense indexes
        bm25 = BM25Retriever.fit(all_chunks)
        dense = DenseRetriever(embeddings, documents=all_chunks)

        return cls(
            chunks_text=all_chunks,
            chunk_doc_idx=chunk_doc_idx,
            chunk_local_idx=chunk_local_idx,
            bm25=bm25,
            dense=dense,
            embedder=active_embedder,
            llm=llm,
            top_k=top_k,
            n_retrieve=n_retrieve,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        query_strategy: str = "direct",
        n_queries: int = 3,
    ) -> Answer:
        """Ask a question over the indexed corpus.

        Steps:
          1. Optionally transform the query (HyDE or multi-query).
          2. Retrieve via BM25 + Dense (one round, or one round per
             rewritten query when ``query_strategy="multi_query"``).
          3. Hybrid-fuse via RRF, take top ``top_k`` after fusion.
          4. Pass the top chunks + the **original** question to the
             LLM with a grounding prompt.
          5. Return the LLM's answer + the citations.

        Args:
            question: natural-language query.
            top_k: override the default citation count for this call.
            query_strategy: how to expand / transform the question.

                - ``"direct"`` (default) — embed the question as-is.
                - ``"hyde"`` — ask the LLM for a short hypothetical
                  answer and embed *that* for dense retrieval.
                  Helps when query and corpus phrasings differ.
                  One extra LLM call.
                - ``"multi_query"`` — ask the LLM to rewrite the
                  question ``n_queries`` times, retrieve over each,
                  RRF-merge the results. One extra LLM call.

            n_queries: number of LLM rewrites for ``"multi_query"``.
                Ignored otherwise. Default 3 (4 total searches).

        Returns:
            An :class:`Answer` with the LLM's response and source chunks.

        Note:
            All strategies use the **original** question for the final
            answer-generation prompt — only retrieval is changed. So
            the LLM still sees the user's actual phrasing in step 4.
        """
        if not question.strip():
            raise ValueError("ask() requires a non-empty question")
        if query_strategy not in {"direct", "hyde", "multi_query"}:
            raise ValueError(
                f"Unknown query_strategy={query_strategy!r}. "
                "Use 'direct', 'hyde', or 'multi_query'."
            )

        k = top_k if top_k is not None else self.top_k

        # 1. Retrieve — branch on query_strategy
        if query_strategy == "direct":
            bm25_hits = self.bm25.search(question, top_k=self.n_retrieve)
            query_vec = self.embedder.embed(question)
            dense_hits = self.dense.search(query_vec, top_k=self.n_retrieve)
        elif query_strategy == "hyde":
            from nom.rag.queries import hyde

            # BM25 still uses the question (keyword overlap is the point);
            # dense uses the LLM's hypothetical answer (richer vocabulary
            # closer to corpus prose).
            hypothetical = hyde(question, self.llm)
            bm25_hits = self.bm25.search(question, top_k=self.n_retrieve)
            query_vec = self.embedder.embed(hypothetical)
            dense_hits = self.dense.search(query_vec, top_k=self.n_retrieve)
        else:  # multi_query
            from nom.rag.queries import multi_query as _mq

            queries = _mq(question, self.llm, n=n_queries)
            bm25_lists = [self.bm25.search(q, top_k=self.n_retrieve) for q in queries]
            dense_lists = [
                self.dense.search(self.embedder.embed(q), top_k=self.n_retrieve) for q in queries
            ]
            # Flatten per-side: pre-fuse each side's per-query results, so
            # downstream hybrid_score still sees one bm25 list and one
            # dense list.
            bm25_hits = hybrid_score(
                bm25_lists, method="rrf", top_k=self.n_retrieve, rrf_k=self.rrf_k
            )
            dense_hits = hybrid_score(
                dense_lists, method="rrf", top_k=self.n_retrieve, rrf_k=self.rrf_k
            )

        # 2. Hybrid fuse
        fused = hybrid_score(
            [bm25_hits, dense_hits],
            method="rrf",
            top_k=k,
            rrf_k=self.rrf_k,
        )
        n_retrieved = len({h.idx for h in bm25_hits} | {h.idx for h in dense_hits})

        if not fused:
            return Answer(
                text="No relevant context found in the indexed corpus.",
                citations=[],
                n_retrieved=0,
            )

        # 3. Build citations from the fused hits
        citations: list[Citation] = []
        context_blocks: list[str] = []
        for rank, hit in enumerate(fused, start=1):
            text = hit.text or self.chunks_text[hit.idx]
            citations.append(
                Citation(
                    doc_idx=self.chunk_doc_idx[hit.idx],
                    chunk_idx=self.chunk_local_idx[hit.idx],
                    score=hit.score,
                    text=text,
                )
            )
            context_blocks.append(f"[{rank}] {text}")

        # 4. LLM call with grounding prompt
        prompt = _build_prompt(question, context_blocks)
        response = self.llm.complete(prompt, max_tokens=2048)

        return Answer(
            text=response.strip(),
            citations=citations,
            n_retrieved=n_retrieved,
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _source_to_text(source: str | Path | bytes) -> str:
    """Convert any supported source to a single text string.

    Routes through ``nom.doc`` for paths / bytes:
    Load → Parse → OCR (when needed) → Normalize. Plain strings (not
    looking like a path) are returned as-is.

    The OCR stage runs only when ``Parse`` flagged unindexable pages
    (image inputs and image-only PDF pages). If pytesseract isn't
    installed we degrade gracefully — the unindexable pages stay empty
    and the caller sees a zero-chunk material, not a hard failure.
    """
    if isinstance(source, str) and not _looks_like_path(source):
        return source

    from nom.doc import OCR, Context, Load, Normalize, Parse

    ctx = Context(source=source)
    Load().run(ctx)
    Parse().run(ctx)
    if ctx.needs_ocr:
        # pytesseract not installed → skip OCR rather than failing the
        # whole upload. User gets empty extraction; visible as 0 chunks.
        with contextlib.suppress(ImportError):
            OCR().run(ctx)
    Normalize().run(ctx)
    return ctx.text


def _looks_like_path(s: str) -> bool:
    """Heuristic: short string with a recognized extension and existing on disk."""
    if len(s) > 4096 or "\n" in s:
        return False
    p = Path(s)
    return p.is_file()


def _build_prompt(question: str, context_blocks: list[str]) -> str:
    """Construct a grounding prompt for the LLM.

    The prompt asks the model to:
    - Answer in the same language as the question (VN ↔ EN auto).
    - Cite the bracketed chunk numbers it relied on.
    - Refuse to fabricate when the context is insufficient.
    """
    context = "\n\n".join(context_blocks)
    return (
        "You are a Vietnamese-aware document Q&A assistant. Answer the user's "
        "question using ONLY the context blocks below. Cite the relevant block "
        "numbers like [1] [2] inline. If the context does not contain the answer, "
        "say so plainly — do not fabricate. Match the language of the question.\n\n"
        f"=== Context ===\n{context}\n\n"
        f"=== Question ===\n{question}\n\n"
        "=== Answer ==="
    )
