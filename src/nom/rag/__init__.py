"""High-level RAG pipeline — the easy-to-use front door.

Three lines from documents to answers::

    from nom.rag import RAG
    from nom.llm import Ollama

    rag = RAG.from_documents(
        ["contract.pdf", "letter.pdf", "Hợp đồng số HD-001..."],
        llm=Ollama(model="qwen3:8b"),
    )

    answer = rag.ask("Có bao nhiêu hợp đồng có phạt vi phạm?")
    print(answer.text)         # the LLM's response
    print(answer.citations)    # [(doc_idx, chunk_idx, score), ...]

Under the hood, ``RAG`` composes the v0.0.x building blocks:

  Files / strings
        │
        ▼
  nom.doc.Pipeline    (PDF/image/text → clean text per doc)
        │
        ▼
  nom.chunking        (text → 512-token chunks, sentence-boundary)
        │
        ▼
  nom.embeddings      (chunks → vectors, VN-tuned)
        │
        ▼
  nom.retrieve        (BM25 + Dense + hybrid RRF)
        │
        ▼
  nom.llm             (top-k chunks + question → answer)

You can swap any layer (Embedder, LLM, retriever) by passing a
different instance to :meth:`RAG.from_documents`. The Protocol
contracts of each submodule are the seam.
"""

from nom.rag.pipeline import RAG, Answer, Citation

__all__ = ["RAG", "Answer", "Citation"]
