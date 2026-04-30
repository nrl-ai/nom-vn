# Nôm — Architecture

A **single library** with a clear submodule boundary. One repo, one PyPI package (`nom-vn`), one Apache 2.0 license. Submodules are individually pip-installable via extras so users don't pay for what they don't use.

The architecture follows two non-negotiable principles from our internal operating manual:

- **Principle 11 — Audit dependencies before adopting.** Pickle/opaque-binary deps auto-reject. Prefer in-tree reimplementation when feasible. Document every dep's license, format, and audit findings in `BENCHMARK.md`.
- **Principle 12 — Verified benchmarks only.** Every metric in user-facing materials traces to a runnable script (with warmup + best-of-N for throughput) or a cited public source.

---

## TL;DR — one library, layered submodules

```
                                       nom (core / Nôm brand)
        ┌──────────────────────────────────┴──────────────────────────────────┐
        │                                                                     │
   ┌────▼────┐  ┌──────┐  ┌──────┐  ┌────────────┐  ┌───────┐  ┌─────────┐  ┌────┐  ┌──────┐
   │  text   │  │ doc  │  │ llm  │  │ embeddings │  │chunk- │  │retrieve │  │rag │  │chat  │
   │         │  │      │  │      │  │            │  │  ing  │  │         │  │    │  │      │
   │ pure-py │  │ Pipe │  │Ollama│  │ VN models  │  │VN-aware│  │BM25 +   │  │one-│  │FastAPI│
   │ no deps │  │-line │  │OpenAI│  │            │  │       │  │ dense + │  │shot │  │+ HTMX│
   │         │  │      │  │Anthr │  │            │  │       │  │ hybrid  │  │+    │  │ UI   │
   │         │  │      │  │      │  │            │  │       │  │         │  │chat │  │      │
   └────┬────┘  └──┬───┘  └──┬───┘  └─────┬──────┘  └───┬───┘  └────┬────┘  └─┬──┘  └──┬───┘
        │         │          │            │             │           │          │        │
        └─────────┴──────────┴────────────┴─────────────┴───────────┴──────────┴────────┘
                                              │
                                              ▼
                            One repo: github.com/nrl-ai/nom-vn
                            One package: nom-vn  (Apache 2.0)
```

| Submodule | Purpose | Status | Hard deps | Extras |
|---|---|---|---|---|
| `nom.text` | Vietnamese text utilities | shipped v0.0.2 | none | — |
| `nom.doc` | PDF/image → typed dict pipeline | shipped v0.0.3 | `pydantic` | `[doc]` adds pdf/ocr |
| `nom.llm` | LLM adapters | shipped v0.0.3 | `pydantic` | `[llm]` adds httpx |
| `nom.embeddings` | Vietnamese embedding adapters | planned v0.0.4 | `pydantic` | `[embeddings]` adds model loader |
| `nom.chunking` | VN-aware document chunking | planned v0.0.4 | `pydantic` | — |
| `nom.retrieve` | BM25 + dense + hybrid scoring | planned v0.0.5 | `pydantic` | — (numpy ships transitively with embeddings) |
| `nom.index` | Vector-store adapters (Chroma, Qdrant, pgvector) | planned v0.1 | `pydantic` | `[index-chroma]`, `[index-qdrant]`, `[index-pg]` |
| `nom.rag` | High-level RAG composition | planned v0.1 | `pydantic` | reuses other extras |
| `nom.chat` | Optional FastAPI app + HTMX UI | planned v0.2 | `pydantic` | `[chat]` adds fastapi, jinja2 |

**One install command grows with use**:

```bash
pip install nom-vn                            # text + doc.schemas only (no PDF/OCR/LLM)
pip install "nom-vn[doc]"                     # + PDF, OCR, image handling
pip install "nom-vn[llm]"                     # + LLM adapters (httpx)
pip install "nom-vn[embeddings,index-chroma]" # + RAG building blocks with Chroma
pip install "nom-vn[all]"                     # everything
pip install "nom-vn[chat]"                    # the deployable chat app
```

---

## Why one library (and not three)

Considered the alternatives and rejected each:

1. **Three separate repos** (toolkit / RAG glue / chat app) — splits the brand, multiplies CI overhead, makes cross-cutting refactors painful, confuses users about which package to install.
2. **Mega-monolith with no extras** — every user pulls every dep including the ones they'll never use; install bloats; audit surface explodes.

**One repo with extras** matches the actual grain: the *brand* (Nôm) is one thing; the *deployment surface* differs per submodule. Extras let `pip` express that.

This also simplifies:
- **Versioning** — one CHANGELOG, one tag, one release
- **Cross-cutting refactors** — change a Stage Protocol in `nom.doc`, update the call sites in `nom.rag` in the same PR
- **Discoverability** — one Github org page, one PyPI page, one docs site
- **Brand integrity** — every part says "Nôm"

---

## Protocol seams & scaling path

Every meaningful boundary in `nom-vn` is a `typing.Protocol` (where it
makes sense, `runtime_checkable`). The fast path is single-process
Python; the cloud path replaces three Protocol implementations and
changes nothing in the application layer. State lives in storage;
computation is stateless. Caching is selective — we cache only what's
expensive to recompute (embeddings), never what isn't (BM25, parsing).

### The seven layers

| Layer | Role | Stateful? | Today's modules |
|---|---|---|---|
| **0 · Primitives** | VN text utilities, chunking | No | `nom.text`, `nom.chunking` |
| **1 · Models** | Embedder, LLM, OCR backends | Yes (lazy-loaded weights) | `nom.embeddings`, `nom.llm`, `nom.doc.OCR` |
| **2 · Retrieval** | BM25, Dense, hybrid fusion | Yes (in-RAM index per corpus) | `nom.retrieve` |
| **3 · RAG** | Compose models + retrieval into ask() | Immutable per-corpus | `nom.rag.RAG` |
| **4 · Storage** | Persistence boundary | Yes (the only durable state) | `nom.chat.Store`, `nom.chat.EmbeddingsCache` |
| **5 · Application** | HTTP + UI bundle, DI factory | No (delegates to Layer 4) | `nom.chat.server.build_app` |
| **6 · Deployment** | CLI, config, packaging | No | `nom.chat.cli`, `pyproject.toml`, `ui/` |

### Where each Protocol seam lives in the code

| Seam | Defined in | Default impl | Future impls (concrete, not hypothetical) |
|---|---|---|---|
| `nom.embeddings.Embedder` | `src/nom/embeddings/base.py` | `VietnameseEmbedder` (BGE-base, 768d) | `AITeamVNEmbedder` (BGE-M3 ft, +27.9% Acc@1 on Zalo Legal — see `docs/sota_vn_2026q2.md`) |
| `nom.llm.LLM` | `src/nom/llm/base.py` | `Ollama` | `OpenAI`, `Anthropic`, `LlamaCppPython` |
| `nom.retrieve.Retriever` | `src/nom/retrieve/base.py` | `BM25Retriever`, `DenseRetriever` (numpy in-RAM) | `FaissRetriever` / `QdrantRetriever` at >100k chunks (planned `nom.index`) |
| `nom.doc.Stage` | `src/nom/doc/stages.py` | `Tesseract` for OCR | `DotsMocrOCR`, `PaddleOcrV5`, `Qwen3VLOCR` (gated on VN-corpus benchmark per principle 12) |
| `nom.chat.Store` | `src/nom/chat/store.py` | `MemoryStore`, `SqliteStore` | `PostgresStore` (~250 LOC `psycopg`, no ORM) |
| `nom.chat.EmbeddingsCache` | `src/nom/chat/embeddings_cache.py` | `LocalDiskCache` (one `.npy` per material), `MemoryCache` | `S3Cache`, `GcsCache`, `RedisCache` |

### Data flow (RAG ingest → query → answer)

```
                   [bytes / paths / strings]
                              │
                  ┌───────────▼───────────┐
                  │  nom.doc.Pipeline     │  Layer 1 (Stage Protocol)
                  │  Load → Parse → OCR   │  swap: Tesseract / dots.mocr / Qwen3-VL
                  │  → Normalize          │
                  └───────────┬───────────┘
                              │   text per doc
                  ┌───────────▼───────────┐
                  │  nom.chunking         │  Layer 0
                  │  smart_chunk()        │  pure Python, no swap
                  └───────────┬───────────┘
                              │   list[Chunk]
                  ┌───────────▼───────────┐
                  │  nom.embeddings       │  Layer 1 (Embedder Protocol)
                  │  embed_batch()        │  swap: dangvantuan / AITeamVN / e5-mistral
                  └───────────┬───────────┘
                              │   (N, D) float32 + texts
                  ┌───────────▼───────────┐
                  │  EmbeddingsCache      │  Layer 4 (Protocol)
                  │  put(material, vecs)  │  swap: LocalDisk / S3 / Memory
                  └───────────┬───────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
   ┌──────────▼─────┐ ┌──────▼────────┐ ┌────▼──────────┐
   │ BM25Retriever  │ │ DenseRetriever│ │ Future:       │  Layer 2
   │  (lexical)     │ │  (cosine)     │ │ FaissRetriever│  swap at >100k chunks
   └──────────┬─────┘ └──────┬────────┘ └────┬──────────┘
              │              │               │
              └──────────────┼───────────────┘
                             │   list[Hit]
                  ┌──────────▼──────────┐
                  │  hybrid_score()     │  Layer 2 (function, no swap)
                  │  RRF fusion         │
                  └──────────┬──────────┘
                             │   ranked context
                  ┌──────────▼──────────┐
                  │  nom.llm.LLM        │  Layer 1 (LLM Protocol)
                  │  complete(prompt)   │  swap: Ollama / OpenAI / Anthropic
                  └──────────┬──────────┘
                             │
                       Answer + citations
```

### Scaling path (concrete, no fantasy numbers)

| Scale | Topology | Store | EmbeddingsCache | Retriever | Net change |
|---|---|---|---|---|---|
| 1 user, laptop | 1 proc | `SqliteStore` | `LocalDiskCache` | BM25 + Dense | (today's default) |
| 1 user, 100K+ chunks | 1 proc | `SqliteStore` | `LocalDiskCache` | swap → `FaissRetriever` | one constructor swap |
| Small team, 1 host | uvicorn workers | `SqliteStore` (WAL) | `LocalDiskCache` (shared volume) | as above | add nginx in front |
| Multi-host / cloud | N stateless app pods | `PostgresStore` | `S3Cache` | `QdrantRetriever` | three Protocol impls, **zero app changes** |
| Multi-tenant SaaS | N pods + auth | as above + tenant scoping | as above + tenant prefix | as above | add auth middleware in `nom.chat.server` |

Throughput / latency numbers per tier are deliberately omitted —
those need a benchmark, not a guess (verified-benchmarks rule).
`benchmarks/perf/` (component-level) and `benchmarks/rag/`
(end-to-end retrieval) are the places to measure for your workload.

### Anti-architecture rules

What we deliberately **don't** build, and why:

1. **No service locator / DI framework.** Pass dependencies through
   constructors. 8+ params is a sign the class is doing too much.
2. **No `…Manager` classes.** If the name doesn't describe what it
   owns, the class probably shouldn't exist.
3. **No abstract base classes for behavior sharing.** Protocols are
   for contracts; module-level helpers are for shared code.
4. **No event-emitter / pub-sub.** Python's call stack is your event
   log.
5. **No "future-proof" generic Repository / Entity / DTO layer.**
   Call things what they are.
6. **No ORM.** SQL is a language; we know it. Direct `sqlite3` /
   `psycopg` keeps query plans visible. (Considered SQLAlchemy /
   SQLModel; rejected — adds ~15 MB of deps to support a one-config
   swap that's already a 7-method Protocol.)
7. **No micro-services until we have ≥3 independently-deployed
   teams.** We have one repo and one developer.
8. **No config framework.** `argparse` + env vars + a single
   `Config` dataclass is enough.

### What we deliberately don't abstract

- **Tokenization** (`nom.text.word_tokenize`) — too foundational;
  swapping invalidates every benchmark. Stays a function call.
- **The fusion algorithm** (`hybrid_score`'s RRF) — too small to
  warrant a Protocol; just a function with a `method` arg.
- **Chunking strategy** — `smart_chunk` is a function, not a service.
  Could grow a `Chunker` Protocol when there's a second strategy
  worth swapping.
- **The HTTP framework** (FastAPI) — replacing it would be more work
  than it's worth. We accept the lock-in.

---

## Module-by-module spec

### `nom.text` — Vietnamese text utilities (shipped, v0.0.2)

Pure-stdlib normalization, tokenization, sentence splitting. Zero hard deps.

```python
from nom.text import normalize, fix_diacritics, word_tokenize, sent_tokenize, text_normalize

normalize("Hợp đồng số 02")              # NFC composition
fix_diacritics("Hop dong nay duoc lap")  # rule-based restoration (~41% baseline)
word_tokenize("Hợp đồng số 02")          # ["Hợp đồng", "số", "02"]
sent_tokenize("Hôm nay. Anh có cần?")    # ["Hôm nay.", "Anh có cần?"]
text_normalize("Hợp đồng  ngày 14, tháng 3.")  # whitespace + punct cleanup
```

### `nom.doc` — Document extraction pipeline (shipped, v0.0.3)

Six-stage Pipeline: Load → Parse → OCR → Normalize → Extract → Validate. All stages real.

```python
from nom.doc import extract
from nom.llm import Ollama

result = extract(
    "hop_dong.pdf",
    schema={"so_hop_dong": str, "ngay_ky": "date", "tong_gia_tri": "amount_vnd"},
    llm=Ollama(model="qwen3:8b"),
)
```

See `docs/pipeline.md` for the full per-stage detail.

### `nom.llm` — LLM adapters (shipped, v0.0.3)

```python
from nom.llm import Ollama, OpenAI, Anthropic   # only Ollama is real today

llm = Ollama(model="qwen3:8b")
llm.complete("Tóm tắt văn bản:", schema=optional_json_schema)
```

`LLM` is a `Protocol` — any class with `complete(prompt, schema, max_tokens) -> str` qualifies. Users can wire custom backends without inheriting from us.

### `nom.embeddings` — Vietnamese embedding adapters (planned v0.0.4)

```python
from nom.embeddings import VietnameseEmbedder, Embedder

embedder: Embedder = VietnameseEmbedder()           # default model
vec = embedder.embed("Hợp đồng số 02")               # → np.ndarray
vecs = embedder.embed_batch([...])                   # → np.ndarray (N, D)
```

**Default model**: `AITeamVN/Vietnamese_Embedding` (BGE-M3 fine-tune on ~300k VN triplets, top performer on [VN-MTEB](https://arxiv.org/html/2507.21500v1)). Apache 2.0 weights, `safetensors` format (deterministic, not pickle).

`Embedder` is a `Protocol`:

```python
class Embedder(Protocol):
    name: str
    dim: int
    def embed(self, text: str) -> NDArray: ...
    def embed_batch(self, texts: list[str]) -> NDArray: ...
```

### `nom.chunking` — VN-aware document chunking (planned v0.0.4)

```python
from nom.chunking import smart_chunk

chunks = smart_chunk(
    text,
    max_tokens=512,
    overlap=64,
    boundary="sentence",      # "paragraph" | "sentence" | "char"
)
# → list[Chunk(text, start, end, n_tokens, metadata)]
```

Pure Python. Uses `nom.text.sent_tokenize` for VN-aware boundaries. Token counts via `nom.text.word_tokenize` (compounds count as 1).

### `nom.retrieve` — In-process retrieval primitives (planned v0.0.5)

```python
from nom.retrieve import BM25Retriever, DenseRetriever, hybrid_score

bm25 = BM25Retriever.fit(corpus_chunks)
dense = DenseRetriever(embedder, embeddings)

bm25_hits = bm25.search(query, top_k=20)
dense_hits = dense.search(embedder.embed(query), top_k=20)
fused = hybrid_score(bm25_hits, dense_hits, alpha=0.5, method="rrf")
```

In-process numpy; no DB. For up to ~100k chunks this is fine — most users never need to graduate.

### `nom.index` — Vector-store adapters (planned v0.1)

```python
from nom.index import ChromaIndex, QdrantIndex, PgVectorIndex, Index

index: Index = ChromaIndex(path="./vectors")
index.upsert(chunks_with_embeddings)
hits = index.query(query_vector, top_k=10)
```

`Index` is a `Protocol`. Each backend is opt-in via extras: `pip install "nom-vn[index-chroma]"`. Users with their own vector store implement the Protocol and skip the extras entirely.

### `nom.rag` — High-level RAG composition (planned v0.1)

```python
from nom.rag import IngestPipeline, RAGSession
from nom.index import ChromaIndex
from nom.embeddings import VietnameseEmbedder
from nom.llm import Ollama

# 1. Setup
index = ChromaIndex(path="./vectors")
embedder = VietnameseEmbedder()
llm = Ollama(model="qwen3:8b")

# 2. Ingest
ingest = IngestPipeline(index=index, embedder=embedder, chunk_size=512)
ingest.add_files(["contracts/*.pdf"])

# 3. Ask
session = RAGSession(index=index, embedder=embedder, llm=llm)
answer = session.ask("Có bao nhiêu hợp đồng có điều khoản phạt vi phạm trên 10%?")
print(answer.text)         # the LLM's answer
print(answer.citations)    # [(doc_id, page, chunk_idx), ...]
```

Composes the lower-level submodules; doesn't add new external concepts. A user who wants a different chunker or a different reranker swaps it in via the Protocol.

### `nom.chat` — Deployable chat app (planned v0.2)

The final headline product: a self-contained web app for Vietnamese
document Q&A. Ships **inside the Python package** so users get the full
experience with ``pip install`` + one CLI command.

```bash
pip install "nom-vn[chat]"
nom serve                    # starts FastAPI + ships pre-built UI
# → opens http://localhost:8080
```

```python
# Or mount in an existing app
from nom.chat import build_app
app = build_app(...)         # returns a FastAPI instance
```

#### User-facing concepts

- **Space** — a folder of documents the user is asking about. Owns its
  own embeddings index. Examples: "2025 Contracts", "HR Policies",
  "Q3 Reports". Users create / rename / delete spaces.
- **Materials** — documents uploaded to a space. PDF / image / text.
  Run through the v0.0.x toolkit on upload: extract → chunk → embed →
  index.
- **Ask** — natural-language Q&A over a space. Answer + cited source
  chunks (page, location). Streamed.
- **History** — past questions per space, persistent.

#### Frontend — ShadCN UI

- **Stack**: React 19 + TypeScript + Vite for build · Tailwind CSS ·
  ShadCN/ui (Radix UI primitives + idiomatic component recipes).
- **Why ShadCN**: copy-in component library, no runtime dependency on
  a UI framework, accessible defaults, MIT-licensed, easy to brand.
- **Design language**: simple, signature, user-friendly. Specifically:
    - **Simple**: every screen has one primary action (create space /
      upload material / ask question). No navigation tree deeper than
      two levels.
    - **Signature**: a recognizable visual identity — restrained
      palette (one accent color), one display typeface for headings,
      consistent spacing, the Nôm character mark in the chrome. The
      same restraint as `nrl.ai` so the brand carries.
    - **User-friendly**: keyboard-driven primary flows, fast
      streaming responses, citations always visible (not hidden behind
      tooltips), graceful empty states with clear next-action prompts.
- **Build artifact**: ``nom/chat/ui/dist/`` (committed pre-built
  assets) so `pip install` ships the UI; users don't need Node.

#### Backend — FastAPI

- Routes for: ``/api/spaces`` (CRUD), ``/api/spaces/{id}/materials``
  (upload, list, delete), ``/api/spaces/{id}/ask`` (streaming Q&A
  with cited chunks), ``/api/spaces/{id}/history``.
- Auth: simple username/password by default (single-user laptop
  deployment); pluggable to OIDC for org deployments.
- Storage: SQLite by default (zero-config, file-based); optional
  Postgres for multi-user.
- Vector index: ``nom.index.ChromaIndex`` per space (file-backed,
  embedded, no server).

#### CLI surface

```bash
nom serve                           # start the web app
nom serve --host 0.0.0.0 --port 8080
nom space create "Contracts 2025"   # CLI alternatives to the UI
nom space upload <id> ./contract.pdf
nom space ask <id> "Bao nhiêu hợp đồng có phạt vi phạm trên 10%?"
```

#### Architecture sketch

```
                  ┌────────────────────────────────────────┐
                  │  Browser  (ShadCN UI / React + Tailwind)│
                  └──────────────────┬─────────────────────┘
                                     │ HTTPS (REST + SSE for streaming)
                  ┌──────────────────▼─────────────────────┐
                  │  FastAPI (nom.chat.server)             │
                  │  /api/spaces · /materials · /ask       │
                  └────┬─────────────────────────────┬─────┘
                       │ uses                        │ uses
              ┌────────▼──────────┐        ┌─────────▼────────────┐
              │  nom.rag          │        │  Auth / Sessions     │
              │  IngestPipeline   │        │  (passlib + JWT)     │
              │  RAGSession       │        └─────────┬────────────┘
              └────────┬──────────┘                  │
                       │                             │
                       ▼                             ▼
             ┌─────────────────────┐  ┌──────────────────────────┐
             │ nom.text/doc/llm    │  │ SQLite (default) or      │
             │ /embeddings/        │  │ Postgres                 │
             │ chunking/retrieve/  │  │ (users, spaces, history) │
             │ index               │  └──────────────────────────┘
             └─────────────────────┘
```

#### What ``nom.chat`` adds on top of ``nom.rag``

- HTTP API + streaming SSE
- Browser UI (built React assets in-tree)
- Space + material + history models (SQLite/Postgres)
- Auth + session management
- ``nom serve`` CLI entry point
- ``Dockerfile`` + ``docker-compose.yml`` for self-host

All shipped in the same ``nom-vn`` package, behind ``[chat]`` extras.

---

## Component picks — lightweight, fast, accurate, local, replaceable

The single hardest design choice for a Vietnamese AI toolkit is which models / engines to default to. Goals, ranked:

1. **Local-first** — everything works offline, no cloud account required
2. **Lightweight** — default install footprint stays small
3. **Fast** — measured throughput / latency, not vibes
4. **Accurate enough** — published benchmark numbers, with citations
5. **Replaceable** — every component sits behind a `Protocol` so users can swap without forking us

For each axis, we ship a **default** (the sweet spot), a **lighter** option (resource-constrained / edge), and document a **higher-accuracy** option (when users have GPU + budget). Defaults install with `pip install nom-vn[<extra>]`; the others are user-installed.

### LLM (local) — `nom.llm`

| Tier | Model | Size on disk | RAM/VRAM | Quality |
|---|---|---|---|---|
| Light | `qwen3:1.7b` (Q4) | ~1 GB | ~2 GB | Acceptable for short extractions |
| **Default** | **`qwen3:8b`** (Q4) | **~5 GB** | **~6 GB** | **Strong VN, runs on consumer laptop** |
| Heavy (cloud or beefy GPU) | `qwen3:32b` (Q4) | ~20 GB | ~24 GB | Top open-weight VN |

- Hosted via **Ollama** (Apache 2.0 server, deterministic structured-output `format=schema` API).
- Adapter: `nom.llm.Ollama(model="qwen3:8b")`.
- Replace with: any class implementing `LLM.complete(prompt, schema=None) -> str`. Cloud adapters (`OpenAI`, `Anthropic`) ship as stubs today, real impls follow same Protocol.

**Why Qwen3 over Llama-3 for VN default**: Qwen3 holds Apache 2.0, supports >100 languages (strong VN per `vmlu.ai/leaderboard`), and ships in 1.7B/8B/32B sizes covering the full lightweight→heavy axis. Llama-3 has restrictive license terms; Qwen3 has none.

### Embeddings (local) — `nom.embeddings`

| Tier | Model | Size | Dim | Quality (VN-MTEB) |
|---|---|---|---|---|
| Light | `paraphrase-multilingual-MiniLM-L12-v2` | ~120 MB | 384 | Multilingual, decent VN |
| **Default** | **`dangvantuan/vietnamese-embedding`** | **~440 MB** | **768** | **84.87 STS Pearson — top of public VN-MTEB at its size class** |
| Heavy | `AITeamVN/Vietnamese_Embedding` (BGE-M3 fine-tune) | ~2 GB | 1024 | Highest reported VN retrieval quality |

- All three are **`safetensors`** format (deterministic, not pickle — passes our no-pickle policy).
- Apache 2.0 weights for default + heavy; MIT for light.
- Adapter: `nom.embeddings.VietnameseEmbedder()` (default), constructor accepts an alternative `model_name=...`.
- Replace with: any class implementing `Embedder.embed(text) -> ndarray` + `embed_batch`.

### Tokenizer / Sentence splitter (local) — `nom.text`

| Tier | Approach | Size | Throughput | Boundary agreement vs upstream |
|---|---|---|---|---|
| **Default (and only)** | **Pure-Python rule-based with curated compound table** | **~30 KB** | **734k tok/s** | **77.77% Jaccard vs underthesea CRF** |

Already shipped (v0.0.2). Zero deps, zero binaries. v0.0.3 plan: train our own CRF/transformer to close the gap, ship weights with checksums and a public training script.

Replace with: any callable matching `word_tokenize(text) -> list[str]`. (Not a Protocol class — just a function shape.)

### OCR (local) — `nom.doc.OCR`

| Tier | Engine | Size | Accuracy on VN scans (cited) |
|---|---|---|---|
| Light (default) | **Tesseract 5 + `vie` traineddata** | **~30 MB** + 5 MB lang pack | **70-97% (image-quality dependent)** |
| Heavy (opt-in) | PaddleOCR PP-OCRv5 | ~500 MB | 94.5% on OmniDocBench |

- Tesseract is system-installed (`apt install tesseract-ocr tesseract-ocr-vie` on Debian/Ubuntu, `brew install tesseract tesseract-lang` on macOS).
- pytesseract is a thin wrapper (~hundreds of LOC).
- Replace with: any class matching `OCR.run(ctx)` Stage Protocol.

### PDF parsing (local) — `nom.doc.Parse`

| Tier | Library | Size | Speed | License |
|---|---|---|---|---|
| **Default** | **pdfplumber (+ pdfminer.six)** | **~3 MB** | 0.5×–1× | **MIT (permissive)** |
| Heavy (opt-in) | PyMuPDF / fitz | ~30 MB | 19× faster | **AGPL** (license-restricted) |

Permissive license wins the default slot. Users who can comply with AGPL get the speed bump via `Parse(backend="pymupdf")`.

### Vector store (local) — `nom.index` (planned v0.1)

| Tier | Backend | Size | Ops/s (rough) | When to pick |
|---|---|---|---|---|
| Tiny | In-process numpy (`nom.retrieve.DenseRetriever`) | 0 (already in core) | bounded by RAM | <100k chunks, prototyping, tests |
| **Default** | **ChromaDB (local, embedded)** | **~50 MB** | **~5k qps for top-10 over 1M vectors** | Most apps |
| Heavy | Qdrant (separate server) | ~80 MB binary + server | ~50k qps | Production / multi-tenant |
| Existing infra | pgvector | uses your Postgres | depends on PG | Teams with Postgres already |

- Each lives behind `[index-chroma]`, `[index-qdrant]`, `[index-pgvector]` extras. Users install only what they need.
- All implement the same `Index` Protocol — apps swap backends without code changes beyond construction.

### Chunking — `nom.chunking` (planned v0.0.4)

Pure-Python, no models, no deps. Uses `nom.text.sent_tokenize` + `word_tokenize` for VN-aware boundaries. Sizes are negligible.

### Reranker (optional) — `nom.rag.Reranker` (planned v0.1+)

| Tier | Approach | Size | Notes |
|---|---|---|---|
| **Default** | **None** — hybrid BM25+dense usually sufficient | 0 | Skip the layer entirely |
| Light (opt-in) | `cross-encoder/ms-marco-MiniLM-L-6-v2` | ~80 MB | Fast, multilingual, good enough for English-heavy mixed input |
| VN-tuned | (Open question — see "Open questions" below) | TBD | We may train our own; track v0.0.3+ |

### Diacritic restoration — `nom.text.fix_diacritics`

| Tier | Approach | Word accuracy on our corpus | Notes |
|---|---|---|---|
| **Default (shipped)** | Rule-based table (~120 entries) | **~41%** (measured) | Zero deps, instant |
| v0.0.3 plan | DistilBERT-Viet wrapper OR our own char-level model | targeting >90% | Behind `[diacritics]` extra; weights shipped with checksum |

The v0.0.3 component will be picked based on measured accuracy *and* model size — leaning toward training a small in-tree model so we can ship weights without depending on a third-party HuggingFace ID we don't control.

---

## Replaceability — every default is a Protocol

Every component above sits behind a typing Protocol. Users replace the default by writing their own class with the same shape — no inheritance from us, no import of our base class, no decorator magic.

```python
# Example: swap the LLM with a hosted provider
from nom.doc import extract

class MyAzureOpenAI:
    name = "azure-openai"
    def complete(self, prompt, *, schema=None, max_tokens=2048):
        # ...your code...
        return response_text

result = extract("doc.pdf", schema={...}, llm=MyAzureOpenAI())
```

```python
# Example: swap the Embedder with a custom domain-trained model
from nom.embeddings import Embedder
import numpy as np

class LegalDomainEmbedder:
    name = "legal-vn"
    dim = 768
    def embed(self, text: str) -> np.ndarray: ...
    def embed_batch(self, texts: list[str]) -> np.ndarray: ...
```

```python
# Example: swap the entire Pipeline composition
from nom.doc import Pipeline, Load, Parse, Normalize, Extract, Validate

# Skip OCR + Normalize for known-clean text input
pipe = Pipeline([Load(), Parse(), Extract(my_llm), Validate()])
```

The published Protocol surface is intentionally small. Adding capabilities (streaming, batching, async) is additive — existing implementations keep working.

---

## Cross-cutting design rules

### 1. Hard deps stay tiny

- **`pydantic`** is the only required runtime dep. Every other module's needs go behind extras.
- A user who only wants `fix_diacritics` pays nothing for `nom.chat`'s FastAPI dep.

### 2. Protocol-first interfaces (no ABC inheritance)

Every public IO surface is a `typing.Protocol`. Users implement protocols in their own classes without importing our base classes. This keeps the dependency arrow pointing the right way.

Protocols already shipped or planned:
- `LLM.complete(prompt, schema=None) -> str` — `nom.llm` (shipped)
- `Stage.run(ctx) -> Context` — `nom.doc` (shipped)
- `Embedder.embed(text) -> ndarray` — `nom.embeddings` (planned)
- `Index.upsert/query` — `nom.index` (planned)
- `Reranker.score(query, docs)` — `nom.rag` (planned)

### 3. Explicit submodule boundaries

| Layer | Imports allowed |
|---|---|
| `nom.text` | stdlib only |
| `nom.doc` | stdlib + `nom.text` + `[doc]` extras |
| `nom.llm` | stdlib + `[llm]` extras |
| `nom.embeddings` | stdlib + `[embeddings]` extras |
| `nom.chunking` | stdlib + `nom.text` |
| `nom.retrieve` | stdlib + `nom.embeddings` + `nom.chunking` |
| `nom.index` | stdlib + `nom.retrieve` + `[index-*]` extras |
| `nom.rag` | stdlib + `nom.{doc,llm,embeddings,chunking,retrieve,index}` |
| `nom.chat` | all of the above + `[chat]` extras |

Enforced via `import-linter` (or equivalent) in CI when the `nom.rag` work lands.

### 4. Versioning

- **Single semver** (`major.minor.patch`) across the library.
- **Within v0.x**: no removals, only additions and bug fixes. Users can pin `nom-vn>=0.0.x,<1.0` safely.
- **v1.0** when the public Protocols + module structure has stabilized for ~6 months.
- Each release: tag the repo, push to PyPI, append to `CHANGELOG.md`.

### 5. Reproducibility (verified-benchmarks rule)

`benchmarks/` is one tree, organized by concern, not per-submodule:

```
benchmarks/
├── perf/         # nom.text throughput, nom.doc.parse throughput
├── accuracy/     # diacritic recovery, tokenization vs upstream tokenizers
├── retrieval/    # recall@k, ndcg@k on a VN doc-QA corpus
├── ingest/       # pages/sec at given chunk size
├── rag/          # answer faithfulness + citation accuracy
├── data/         # licensed VN corpora (CC0/CC-BY)
└── results/      # baseline JSONs (committed for regression tracking)
```

Numbers in user-facing materials must trace back to a script in this tree. No cold-start results without warmup. No cross-borrowed metrics.

### 6. Dependency audit (no-pickle rule)

Each addition to `pyproject.toml` requires a matching note in `docs/benchmark.md` covering:

1. License (must be permissive — Apache / MIT / BSD / CC0)
2. Bundled artifact format (`.pkl` = auto-reject; safe formats include `safetensors`, `pt` if directly loadable, CRFsuite native binary, ONNX)
3. Why this dep beats reimplementation (quality gap, maintenance cost, etc.)
4. The cited public source for any quality claim

### 7. Release checklist (every version bump)

1. CHANGELOG.md updated under the new version heading
2. `__version__` and `pyproject.toml` version bumped together
3. Benchmark baselines re-run if any code in `benchmarks/perf/` or `benchmarks/accuracy/` could have changed numbers
4. New deps audited and noted in `BENCHMARK.md`
5. CI green (lint + format + types + 3-Python-version test matrix + benchmark smoke)
6. Tag + push + `pypi-publish` workflow

### 8. License — Apache 2.0 throughout

The whole library is Apache 2.0. No dual-licensing, no carve-outs.

The commercial path is **services around the open library** (on-prem deployment support, SLA, custom integration), not license restrictions on the code itself. This keeps the open ecosystem genuinely open and aligns with how durable open infrastructure has historically funded itself.

---

## Decision log

The trade-offs explicitly chosen, recorded so future-us doesn't re-litigate from scratch:

| Decision | Alternative | Why we picked this |
|---|---|---|
| **Single library** | 3 separate repos | One brand, one CHANGELOG, simpler refactors, less user confusion |
| **`pydantic` as hard dep** | optional | Schemas are core to `nom.doc.extract`; making it optional split too many code paths |
| **Vector stores behind extras** | hard dep on Chroma | Users with their own DB shouldn't pay for ours; extras let `pip` express choice |
| **In-process BM25 in `nom.retrieve`** | always go through a vector DB | Useful even without a DB (small corpora, prototyping, tests) |
| **Protocol-first** | ABC inheritance | Users don't need to import our base classes to satisfy the contract |
| **`nom.chat` as a submodule** | separate repo | Same brand, same CHANGELOG, optional via `[chat]` extras |
| **Apache 2.0 throughout** | dual / source-available | Commercial path is services, not license fences |
| **Hybrid retrieval default** | dense-only | Hybrid wins on every public benchmark we've measured |

---

## Migration plan from current state

Where we are now: `nom-vn` v0.0.3 — `text` + `doc` + `llm` shipped at `github.com/nrl-ai/nom-vn`.

The next four releases stay in this same repo:

| Version | Adds | Status |
|---|---|---|
| v0.0.4 | `nom.embeddings.VietnameseEmbedder` + `nom.chunking.smart_chunk` | shipped |
| v0.0.5 | `nom.retrieve` (BM25 + Dense + hybrid) | shipped |
| **v0.0.6** | **DenseRetriever retune** — 9 ms → 0.034 ms p50 (~264×) | shipped |
| v0.1 | `nom.index` (Chroma adapter default; Qdrant + pgvector follow) + `nom.rag` (IngestPipeline + RAGSession) | next |
| **v0.2** | **`nom.chat` — FastAPI server + ShadCN UI shipped pre-built. ``nom serve`` CLI launches the full app. Spaces / materials / Q&A flows.** | follow |

Every release ships with corresponding benchmark numbers (per principle 12), CHANGELOG entry, and an audit note for any new dep (per principle 11).

---

## Open questions

These are the hard architectural choices we haven't fully decided yet. Flagging here so future-us doesn't re-litigate from scratch.

1. **Embedding cache layer** — should `nom.embeddings` cache embeddings on disk (e.g. SQLite KV) so repeated queries don't re-embed? Or push that to `nom.rag.IngestPipeline`?
2. **Streaming Extract** — Ollama supports streaming. The Extract stage currently waits for full output before parsing JSON. Should we add a streaming variant for chat use cases?
3. **`nom.rag` async-first vs sync-first** — `nom.text` / `nom.doc` are sync. `nom.chat` will need async for websockets. Where does the conversion happen — inside `nom.rag` or only at the chat-app boundary?
4. **Multi-tenant doc isolation** — does `nom.rag` know about tenants, or is that purely `nom.chat`? Leaning `nom.chat`.
5. **Cross-encoder rerank model choice** — there's no widely-adopted VN cross-encoder. Train our own (per the v0.0.3 plan to train a tokenizer)? Use a multilingual reranker?

Each gets resolved at its corresponding release-design phase. Don't let an unanswered question block a submodule that doesn't depend on the answer.
