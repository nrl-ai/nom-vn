# Using nom-vn inside agentic frameworks

`nom-vn` is a **library**, not a framework. It provides Vietnamese-first
RAG primitives (Embedder, Retriever, LLM, RAG, Stage). Whatever
agentic framework you already use can call those primitives directly.

This directory shows the smallest correct wrapper for each major
framework. None of the snippets pull a framework dep into `nom-vn`
itself — they live in the framework's own runtime, importing `nom`
as a normal library.

| Framework | Doc | Wraps |
|---|---|---|
| Google ADK | [adk.md](adk.md) | nom.rag.RAG → ADK Tool, nom.llm → LLM model connector |
| LangChain | [langchain.md](langchain.md) | nom.retrieve.Retriever → BaseRetriever, nom.llm → LLM |
| Pydantic AI | [pydantic_ai.md](pydantic_ai.md) | nom.rag.RAG → Agent tool |

## Why we don't take any of these as a hard dep

- **Layer mismatch.** Frameworks own the *agent loop* (Runner, Session,
  Memory). nom-vn provides the *data side*. Pulling a framework as a
  dep would force every nom-vn user to adopt that framework's whole
  worldview.
- **Churn rate.** LangChain rewrote its core API twice in 2025. ADK is
  6 months old in production. Pydantic AI, Letta, smolagents, CrewAI
  are all active in 2026 — nobody has won. Coupling nom-vn to one
  ages the project fast.
- **License governance.** ADK is Apache 2.0 (fine), LangChain is MIT
  (fine), but their *release cadence* is not under our control. A
  vendor breaking change shouldn't break nom-vn users.

So: nom-vn is the upstream Vietnamese-data library. Frameworks consume
it. The wrappers in this directory are the seam.

## What works without any wrapper

Anything that accepts a callable. Most modern agent frameworks let you
register a Python function as a tool — just expose what nom-vn does:

```python
from nom.rag import RAG

rag = RAG.from_documents(["doc1.pdf", "doc2.txt"])

def search_vn_docs(question: str) -> str:
    """Tìm kiếm trong corpus tiếng Việt và trả về câu trả lời với trích dẫn."""
    return rag.ask(question).text

# Register `search_vn_docs` with whatever your framework uses.
```

That single function is enough for ~80% of use cases. Read the
per-framework docs for the few extras that are worth it (streaming
hooks, structured output, citation passthrough).
