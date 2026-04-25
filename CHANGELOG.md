# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] — 2026-04-25

### Advanced RAG — opt-in query strategies

`RAG.ask()` gained a `query_strategy=` kwarg with three options:

- **`"direct"`** (default, unchanged behavior) — embed the question
  as-is and retrieve.
- **`"hyde"`** — Hypothetical Document Embeddings (Gao et al. 2022).
  Asks the LLM to write a short hypothetical answer, then embeds
  *that* for dense retrieval. BM25 still uses the question. One
  extra LLM call. Helps when query and corpus phrasings differ.
- **`"multi_query"`** — LLM rewrites the question `n_queries` times
  (default 3 → 4 total searches), retrieves over each, RRF-merges
  the results. One extra LLM call. Smooths brittleness from a
  single phrasing.

In all three strategies, the **final answer-generation prompt** still
uses the user's original question — only retrieval is changed. So
the LLM sees the actual phrasing in step 4.

The query helpers ship as standalone exports too, for users wiring
nom-vn into other agentic frameworks:

```python
from nom.rag import hyde, multi_query
from nom.llm import OpenAI

llm = OpenAI()
hypothetical = hyde("Quyền cơ bản của công dân?", llm)
queries = multi_query("Quyền cơ bản?", llm, n=3)  # ["Quyền…", *3 rewrites]
```

10 new tests in `tests/test_rag.py` covering the strategies and the
standalone helpers (deterministic — no real LLM calls).

**No quality numbers claimed.** Per CLAUDE.md principle 12, we won't
publish "X% improvement" without a real VN benchmark corpus
(Zalo Legal QA being the obvious target). The primitives ship; the
quality claims wait.

## [0.2.3] — 2026-04-25

### Cloud LLM adapters — OpenAI + Anthropic now real

`nom.llm.OpenAI` and `nom.llm.Anthropic` previously raised
`NotImplementedError`. Both now ship as full adapters implementing
the same `LLM` Protocol as `Ollama`, so existing call sites
(`nom.doc.Extract`, `nom.rag.RAG`, `nom.chat`) work with cloud
models by constructor swap alone.

- **`nom.llm.OpenAI`** (~155 LOC) — chat completions over httpx.
  `response_format=json_schema` strict mode for structured output.
  Critically: `base_url=` makes the same adapter work for any
  OpenAI-compatible endpoint (Azure / DeepSeek / OpenRouter /
  LiteLLM / vLLM / Together / Groq / etc.). Default model:
  `gpt-4o-mini`.
- **`nom.llm.Anthropic`** (~165 LOC) — Messages API over httpx.
  Tool-use pattern with forced `tool_choice` for structured
  output (Anthropic's recommended path for guaranteed-shape JSON).
  Default model: `claude-haiku-4-5-20251001`.
- API keys read from `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` env
  vars by default; `api_key=` constructor kwarg overrides.
- 27 new tests in `tests/test_llm.py` covering both adapters
  (mocked HTTP — no live calls in CI).
- `scripts/smoke_cloud_llms.py` for live verification — reads
  `.env`, sends one VN prompt through each configured provider.
- `.env.example` template; `.env` gitignored.

### Documentation — using nom-vn inside agent frameworks

New `docs/integrations/` directory with concrete wrappers showing
nom-vn as a library inside other agentic frameworks (we don't take
any framework as a hard dep — see `docs/integrations/README.md`
for the rationale):

- `docs/integrations/adk.md` — Google ADK (`nom.rag.RAG` as a
  `FunctionTool`, `nom.llm` as an `LlmAgent` model)
- `docs/integrations/langchain.md` — LangChain (`nom.rag` as
  `BaseRetriever`, `nom.llm` as `BaseChatModel`)
- `docs/integrations/pydantic_ai.md` — Pydantic AI (`@agent.tool`)

### Scanned-PDF OCR — was NotImplementedError

`OCR` stage previously raised `NotImplementedError` for PDFs whose
pages had no text layer ("convert to images first"). Now it
rasterizes each flagged page via `pdfplumber.page.to_image()` at
200 DPI and OCRs the rendered image. Scanned-PDF Q&A end-to-end
works in `nom serve` (verified on a 3-page synthetic VN business
report — `~3.5s/page` on CPU with `tesseract-ocr-vie`).

### UI — viewer fixes (Material modal)

- **PDF viewer collapsed**: `DialogContent` had `max-h-[90vh]` but
  no `h-[…]`, so nested `flex-1`/`h-full` children collapsed and
  the iframe rendered at ~190 px tall. Added explicit `h-[85vh]`,
  cascades to PDF / image / DOCX / XLSX / PPTX viewers and the
  Extracted-text scroll area.
- **Modal flicker on open**: `animate-fade-in` keyframe set
  `transform: translateY(4px) → translateY(0)`, which overrode
  Radix Dialog's `-translate-x-1/2 -translate-y-1/2` centering
  transform during the 220 ms animation — visibly the dialog
  jumped to its centered position when the animation ended. Added
  a separate `animate-dialog-in` (opacity-only) keyframe just for
  Radix Dialog content/overlay.
- **Tab persistence across materials**: tab state (`original` /
  `extracted`) persisted between modal close/open cycles, so
  opening a new material briefly showed the previous tab before
  the user's click registered. Added `useEffect` to reset to
  `original` on `material.id` change.
- Wider modal: `max-w-4xl` → `max-w-5xl` (more room for DOCX
  paragraphs and PPTX slides).

### Fixes

- **`nom.__version__`** was `"0.2.1"` while `pyproject.toml`
  shipped `"0.2.2"`. Now both `0.2.3`. Upstream consumers that
  read `nom.__version__` will see the correct value.
- `tests/__init__.py` added so `from tests._fakes import ...` works
  on a fresh clone (previously relied on `sys.path` quirks).
- Repo references swept: `nrl-ai/nom` → `nrl-ai/nom-vn` across
  README, docs, and source comments to match the renamed GitHub
  repository.

### Removed

- `nom.llm._CloudStub` (placeholder for OpenAI / Anthropic). Real
  adapters now live in `nom.llm.openai` and `nom.llm.anthropic`.

## [0.2.2] — 2026-04-25

### Architecture — Protocol seams promoted

Two new `runtime_checkable` Protocols formalize the swap points in the
chat layer. Both have multiple shipping implementations and conformance
tests that catch shape drift.

- **`nom.chat.Store`** is now a Protocol (was duck-typed). The
  in-memory class was renamed `MemoryStore`. `SqliteStore` continues
  to conform. `isinstance(store, Store)` works at boot and in tests.
- **`nom.chat.EmbeddingsCache`** is a new Protocol pulled out of
  `SqliteStore`'s inline `.npy` operations. Two impls ship today:
  `LocalDiskCache` (one `.npy` per material — the previous behavior)
  and `MemoryCache` (dict-backed, for tests / ephemeral). Future
  `S3Cache` / `GcsCache` / `RedisCache` slot in unchanged.
- `SqliteStore.__init__` gained an optional `embeddings_cache=` kwarg.
  Default is `LocalDiskCache(data_dir / "embeddings")` — bit-for-bit
  the same as 0.2.1 on disk.

### Added — `AITeamVNEmbedder` (heavier, higher-quality VN embedder)

New opt-in embedder. Loads `AITeamVN/Vietnamese_Embedding` (BGE-M3
fine-tune for VN, 1024-d, ~2.3 GB, Apache 2.0, safetensors).

```python
from nom.embeddings import AITeamVNEmbedder
e = AITeamVNEmbedder()  # cheap; lazy-loads on first .embed()
```

Reported quality (verified on the model card, Zalo Legal QA held-out
20% split): **Acc@1 0.7274 vs 0.5682 base BGE-M3 (+27.9%)**, MRR@10
**0.8181 vs 0.6822**. Source:
https://huggingface.co/AITeamVN/Vietnamese_Embedding.

`VietnameseEmbedder` (BGE-base ft, 768-d, ~440 MB) remains the
default — `AITeamVNEmbedder` is opt-in for users with the disk +
RAM and a legal/formal corpus where the gain applies. Re-bench
against your own corpus via `benchmarks/rag/bench_rag_vn.py` before
promoting it your default for non-legal text.

### Fixed — BGE-M3 ranking claim in `nom.embeddings` docstring

The module docstring at `src/nom/embeddings/__init__.py:18` previously
claimed BGE-M3 is the VN-MTEB #1 at 64.90 overall. Per Table 3 of
[arXiv 2507.21500](https://arxiv.org/html/2507.21500v1), the actual
top of that table is `intfloat/multilingual-e5-large-instruct` at
**67.99**, with `intfloat/e5-mistral-7b-instruct` (67.67) and
`Alibaba-NLP/gte-Qwen2-7B-instruct` (65.84) above BGE-M3 (~4th).
Corrected per CLAUDE.md principle 12.

### Docs — `docs/architecture.md` extended

New section "Protocol seams & scaling path" added at the top:
- **Seven-layer model** (Primitives / Models / Retrieval / RAG /
  Storage / Application / Deployment) with the modules at each layer.
- **Protocol-seam table** mapping each seam to its definition file,
  default impl, and concrete future impls.
- **Data-flow diagram** (RAG ingest → query → answer) showing where
  each Protocol plugs in.
- **Scaling-path table** (1 user → 100K chunks → small team → cloud
  → SaaS) with the swap deltas at each tier.
- **Anti-architecture rules** — what we deliberately don't build
  (no ORM, no DI framework, no event bus, no Manager classes,
  no future-proof generic Repository/Entity/DTO layers, …).

### Added — VN RAG retrieval benchmark (`benchmarks/rag/`)

Reproducible measurement harness for the retrieval half of `nom.rag`:
Recall@{1,3,5,10}, MRR@10, per-query p50/p95 latency. Pluggable
embedder (`fake` for offline / CI; `vietnamese` for real signal) and
pluggable corpus loader.

```bash
python benchmarks/rag/bench_rag_vn.py                       # offline
python benchmarks/rag/bench_rag_vn.py --embedder vietnamese # real
```

Committed:
- `benchmarks/rag/bench_rag_vn.py` — the harness, ~350 LOC.
- `benchmarks/rag/fixtures/vn_legal_tiny.json` — 12 paraphrased VN
  legal articles + 12 questions (Luật Doanh nghiệp 2020, Bộ luật
  Dân sự 2015, Bộ luật Lao động 2019, Luật Đất đai 2024).
- `benchmarks/rag/baselines/vn_legal_tiny__fake_embedder.json`
- `benchmarks/rag/baselines/vn_legal_tiny__vietnamese_embedder.json`
- `benchmarks/rag/README.md` — methodology + path to scaling against
  Zalo Legal QA full corpus.

Honest read of the committed baselines: every retriever saturates
(recall@1 = 1.000, mrr@10 = 1.000) on the tiny fixture with the real
embedder. The fixture **validates the harness; it does not differentiate
retrievers**. To rank retrievers (and to honestly evaluate GraphRAG /
agentic methods later), we need a larger, harder corpus where recall@1
lands well below 1.0 — Zalo Legal QA is the next step (download
documented in the README).

A finding from the **fake-embedder** baseline (dense = noise): hybrid
RRF on signal + noise scored *worse* than the strong leg alone (BM25
recall@1 1.000 → hybrid 0.750). RRF assumes equally-informative
retrievers; when one is noise it dilutes the strong signal. Documented
in the README as a known property.

### Added — React + ShadCN UI (NotebookLM-style)

The chat web app now ships a comprehensive React/TypeScript frontend
in addition to the FastAPI backend. Three-pane editorial layout modeled
on NotebookLM: spaces sidebar / chat thread / sources + studio.

```bash
cd ui && pnpm install && pnpm build   # one-time UI build
nom serve                              # FastAPI auto-detects ui/dist
```

Stack:
- **Vite + React 18 + TypeScript** — strict mode, no untyped surface.
- **TanStack Query (React Query) v5** — typed hooks per endpoint
  (`useSpaces`, `useUploadMaterial`, `useAsk`, …) with optimistic
  invalidation.
- **Radix UI primitives** — Dialog, Tooltip, ScrollArea, Separator —
  copied-in (ShadCN pattern), no runtime npm-on-us dep.
- **Tailwind CSS** — design tokens encode the editorial palette
  (cream `#f1ede3` / ink `#141414` / burnt orange `#c46a37`), sharp
  corners (`border-radius: 0`), Space Grotesk display + Inter body +
  ui-monospace for `§` section markers.
- **react-resizable-panels** — desktop 3-pane split; mobile collapses
  to a single chat column with floating sheet drawers.

Features:
- Per-space localStorage chat history with Cmd/Ctrl+Enter to send,
  Esc to clear.
- Inline citation chips `[1]` `[2]` with hover-tooltip preview and
  click-expand "Sources" panel showing the cited chunks.
- Drag-and-drop multi-file upload zone.
- Empty / loading / error states polished. Suggested Vietnamese
  questions pre-populate when a space has materials but no chat
  history yet.
- Studio panel placeholders (Briefing doc / Mind map / FAQ / Audio
  overview) labeled `v0.3` — honest about what isn't built.

Server integration:
- `nom.chat.server.build_app` auto-discovers `ui/dist/` (or
  `src/nom/chat/ui_dist/` when packaged) via `_find_ui_dist()` and
  mounts it; falls back to the embedded HTML when the bundle is
  absent (chat-only installs still work).
- New `scripts/build_ui.sh` runs `pnpm build` and stages the output
  under `src/nom/chat/ui_dist/` so `pip wheel .` ships the UI.
- `[tool.hatch.build.targets.wheel] artifacts = ["src/nom/chat/ui_dist/**"]`
  ensures the staged bundle is included in the wheel.

### Engineering — SqliteStore refinements (post-simplify pass)
The persistence layer landed in 0.2.1 was reviewed in three parallel
agents (reuse / quality / efficiency) and refactored:

- **N+1 fix** — `list_spaces()` now uses two queries (spaces +
  all-materials grouped in Python) regardless of N spaces.
- **Race fix** — `ask()` uses double-checked locking against a
  dedicated `_build_lock`; concurrent first-asks no longer
  double-build the RAG.
- **Bounded LRU cache** — `_rag_cache` capped at 16 spaces by default
  (`cache_max=` constructor arg), evicting least-recently-used.
- **Batched embedding** — pending materials in `_build_rag()` are now
  parsed and chunked first, then a **single** `embed_batch` runs over
  the union of their chunks; previously each material made its own
  `embed_batch` call.
- **Embedder dim validation** — first index records the embedder
  identity in the meta table; subsequent indexings (or reloads from
  cache) raise a clear error if the dim differs, instead of crashing
  inside `np.vstack`.
- **EXISTS instead of COUNT(\*)** on the per-`ask()` material check
  hot path.
- **TOCTOU fix** — `_delete_embedding_file` uses `unlink(missing_ok=True)`.
- `_source_to_text` promoted from private import to public
  `nom.rag.source_to_text`.
- Schema version write guarded — only on first init.

## [0.2.1] — 2026-04-25

### Added — `nom.chat.SqliteStore` (persistent storage)

`nom serve` now persists state by default — spaces, raw material bytes,
chunked text, and embeddings survive restarts. Cold-start `ask` reads
from disk only; the expensive embed-batch runs **once per material
lifetime**.

```bash
nom serve                          # persistent at ~/.nom (default)
nom serve --data-dir /var/lib/nom  # custom location
nom serve --in-memory              # ephemeral (old behavior)
```

Layout under the data dir:

```
nom.db                 # SQLite — spaces, materials (BLOB), chunks
embeddings/<id>.npy    # one float32 matrix per indexed material
```

`SqliteStore` mirrors the in-memory `Store` shape exactly (duck-typed)
— either can be passed to `build_app(store=...)`. The CLI picks
`SqliteStore` by default and falls back to `Store` only when
`--in-memory` is set.

### Engineering
- 8 new tests (238 total) — `TestSqliteStore` covers create/list,
  cross-restart persistence, embedding cache hit (asserts a fresh
  embedder is **not** called for `embed_batch` after reopen), space
  delete cascading to embedding files, and end-to-end through
  `build_app`.
- Atomic write for embedding files: `<id>.npy.tmp` → `replace()`.
- Crash-safety ordering: write embedding file first (atomic rename),
  then commit chunk rows + flip `indexed=1` in one transaction. A
  crash between leaves at most an orphan `.npy` (harmless, overwritten
  on retry).
- WAL journal mode + foreign-key cascades on the SQLite connection.

## [0.2.0] — 2026-04-25

### Added — `nom.chat` (the deployable web app)

The full v0.2 milestone: Nôm now ships a deployable Vietnamese
document-Q&A web app, launched from the Python package with one CLI:

```bash
pip install "nom-vn[chat]"
nom serve                            # opens http://localhost:8080
nom serve --port 9000 --model phi4
```

Architecture (matches the spec in `docs/architecture.md`):

- **`nom.chat.server.build_app`** — FastAPI factory. Routes:
  `GET /` (UI), `GET/POST/DELETE /api/spaces[/{id}]`,
  `POST/GET /api/spaces/{id}/materials`, `POST /api/spaces/{id}/ask`.
  Each endpoint returns documented JSON with `Hit`-shaped citation
  payloads.
- **`nom.chat.store.Store`** — thread-safe in-memory store for spaces,
  raw material bytes, and one `nom.rag.RAG` per space (lazy-rebuilt
  when materials change). v0.2.1 swaps to SQLite-backed persistence
  behind the same shape — no API changes.
- **`nom.chat.cli`** — `nom serve` entry point with sensible defaults
  (qwen3:8b via local Ollama, port 8080, auto-opens browser).
- **Minimal vanilla-HTML UI** at `/` — three sections: spaces list,
  upload, ask. Inline citations show doc/chunk/score per hit.
  Replaced by React + ShadCN `dist/` in v0.2.1; the swap is a
  one-line `StaticFiles` mount.

### SOTA pointers folded into module docs (April 2026)

- `nom.embeddings` — VN-MTEB (arXiv 2507.21500) lists BGE-M3 #1 at
  64.90 overall; RoPE-based instruction-tuned variants
  (e5-Mistral-7B-Instruct, e5-Qwen2-7B-Instruct) lead at 7B scale.
  All drop in via the same sentence-transformers wrapper.
- `nom.llm` — Phi-4 (MIT, exceptional reasoning per published
  benchmarks) and DeepSeek-V3.2/V4 added as headroom options;
  Qwen3-VL listed as the v0.2.1 vision-direct path.
- `nom.doc` (planned) — `dots.ocr` (rednote-hilab, SOTA multilingual
  VLM document parsing) and Surya (90+ languages, layout + reading
  order) flagged as next-gen alternatives to Tesseract+VietOCR.

### Engineering
- 19 new tests (230 total passing) — `TestClient` exercises the
  FastAPI routes end-to-end with `_FakeLLM` + `_FakeEmbedder` doubles.
  No real model downloads or LLM calls in CI.
- `[chat]` extras: `fastapi`, `uvicorn[standard]`, `python-multipart`.
- `[project.scripts] nom = nom.chat.cli:main` — `nom serve` works
  immediately after install.

## [0.0.7] — 2026-04-25

### Added — `nom.rag` (the easy-to-use front door)

The 3-line happy path is now real::

    from nom.rag import RAG
    from nom.llm import Ollama

    rag = RAG.from_documents(
        ["contract.pdf", "Plain text chunk", "letter.pdf"],
        llm=Ollama(model="qwen3:8b"),
    )
    answer = rag.ask("Bao nhiêu hợp đồng có phạt vi phạm trên 10%?")
    print(answer.text)         # the LLM's response
    print(answer.citations)    # [(doc_idx, chunk_idx, score, text), ...]

`RAG` composes the v0.0.x building blocks: `nom.doc.Pipeline`
(parse + normalize) → `nom.chunking.smart_chunk` → `nom.embeddings`
→ `nom.retrieve` (BM25 + Dense + RRF fusion) → `nom.llm` with a
grounding prompt that demands inline citations.

What's intentional:

- **Sensible defaults**: `embedder` defaults to `VietnameseEmbedder`,
  `top_k=5`, `n_retrieve=20`, `chunk_max_tokens=512`, `overlap=64`.
  Power users override per call.
- **Honest about state**: `from_documents` parses, chunks, embeds,
  and indexes upfront. Cost is documented in the docstring.
- **Protocol seams**: every collaborator (LLM, Embedder) is a
  Protocol — swap defaults without forking the package.
- **Mixed sources**: paths, raw bytes, and plain Python strings are
  all accepted. Strings short enough to look like paths are tried as
  files; otherwise treated as text.
- **Frozen Citation + Answer dataclasses** for deterministic, slot-
  efficient result objects.

Tests: 14 new (211 total passing), all using a `_FakeLLM` + `_FakeEmbedder`
test double so no model downloads or LLM calls happen in CI.

## [0.0.6] — 2026-04-25

### Performance
- **`DenseRetriever` retune** — single-query p50 dropped from 8.98 ms
  to 0.034 ms (~264×) on the 1k × 768-dim baseline. Hot-path changes:
    1. Coerce embeddings to float32 + C-contiguous at construction so
       the matmul never pays the ``astype`` dance per call.
    2. Use ``argpartition(scores, -k)[-k:]`` to find the k largest
       directly, avoiding the negation copy of the full N-element score
       array.
    3. Special-case ``top_k == 1`` to ``argmax`` (skip argsort).
    4. Localize attribute lookups outside the result-building loop and
       split the docs/no-docs branches.
- New baseline: ``benchmarks/results/baseline_retrieve_v0.0.6.json``.
- The v0.0.5 baseline stays in tree as a regression-tracking artifact.

## [0.0.5] — 2026-04-25

### Added
- **`nom.retrieve`** — in-process retrieval primitives. Pure-Python +
  numpy. Three building blocks composable via the `Retriever` Protocol:
    - `BM25Retriever` — Okapi BM25 over `nom.text.word_tokenize`
      (compound-aware). Standard k1=1.5, b=0.75 defaults.
    - `DenseRetriever` — cosine over a precomputed embeddings matrix
      (assumes L2-normalized rows, what `VietnameseEmbedder` produces).
    - `hybrid_score` — RRF (default, parameter-free) or weighted-sum
      score fusion across multiple retrievers.
  Includes `Hit` dataclass (frozen, slots=True) carrying idx + score +
  optional text payload.

### Engineering
- 30 new tests (197 total passing).
- OSS prior art cited in module docstring: rank-bm25 (Apache 2.0,
  reimplemented for VN tokenization), bm25s (MIT, algorithmic shape),
  Cormack et al. SIGIR 2009 (RRF), faiss (rejected at this tier per
  audit policy — bundled binaries).
- Baseline `benchmarks/results/baseline_retrieve_v0.0.5.json` measured
  on 1,000 synthetic VN docs:

    | metric             | value      |
    |--------------------|------------|
    | BM25 build         | 68.0 ms    |
    | BM25 query p50     | 0.372 ms   |
    | BM25 throughput    | 2,692 qps  |
    | Dense query p50    | 8.981 ms   |
    | Dense throughput   | 111 qps    |
    | RRF fusion p50     | 0.038 ms   |

  Dense at 9 ms/query is slower than the matmul math alone suggests —
  candidate for v0.0.6 profiling (numpy overhead, allocator, top-k path).

## [0.0.4] — 2026-04-25

### Added
- **`nom.chunking`** — pure-Python VN-aware document chunking. Three
  boundary modes (sentence/paragraph/character), frozen `Chunk` dataclass,
  zero deps. Measured throughput: 812 docs/sec (sentence mode) on 50 ×
  4.5 KB synthetic VN corpus, baseline at
  `benchmarks/results/baseline_chunking_v0.0.4.json`.
- **`nom.embeddings`** — `Embedder` Protocol + `VietnameseEmbedder` class
  wrapping sentence-transformers (Apache 2.0). Default model:
  `dangvantuan/vietnamese-embedding` (BGE-base VN fine-tune, 768-dim,
  ~440 MB on disk, top public VN STS at its size class). Lazy load —
  `__init__` is dep-free. Always L2-normalizes output.
- New optional dep: `pip install nom-vn[embeddings]` adds
  `sentence-transformers`.
- `benchmarks/perf/bench_chunking.py` — committed throughput bench.
- `benchmarks/perf/bench_embeddings.py` — gated real-model bench
  (skipped if `sentence-transformers` not installed; ~440 MB download
  on first run).

### Engineering
- 34 new tests across the two modules (167 total passing).
- `PPlanning/CLAUDE.md` gained a 4-stage component-build workflow:
  Research → Build → Benchmark → Tune. Each new component must show
  cited OSS prior art, smallest dep surface that meets quality goals,
  warmup + best-of-N benchmarks with committed baselines, and any
  optimization re-measured to confirm it actually helped.

## [Unreleased]

### Added — all six pipeline stages real (v0.1.0-rc)
- **`Load`** (pure stdlib) — magic-byte format detection across PDF / PNG /
  JPEG / GIF / TIFF / BMP / WebP, extension fallback, byte caching.
- **`Parse`** — PDF text extraction via `pdfplumber` (MIT default) with
  `pymupdf` (AGPL) as opt-in alternative.
- **`OCR`** — pytesseract + `vie` traineddata. Image inputs work end-to-end;
  PDF-with-scanned-pages requires v0.1.1 (clear error pointing users at
  `pdftoppm` for now). Configurable lang (default `"vie"`, use `"vie+eng"`
  for mixed) and Tesseract config flags.
- **`Normalize`** — wires `nom.text` (NFC + VN-aware text cleanup), opt-in
  diacritic restoration.
- **`Extract`** — schema-driven LLM extraction with auto-retry on invalid
  JSON. Instructor pattern in ~30 LOC, no extra dep. Strips markdown fences.
- **`Validate`** — Pydantic v2 schema validation with VN coercions
  (date, amount_vnd, party).
- **`Ollama` LLM adapter** — direct httpx call to `/api/chat` with native
  structured-output (`format=schema`). No ollama-python dep.
- **Top-level `extract(source, schema, llm)`** convenience — wraps the
  default 6-stage pipeline. `default_pipeline(llm)` for direct use.
- **End-to-end works** for text + image inputs today. PDF-with-scans is
  the one open path (v0.1.1).
- **64 new tests** — total 133 passing (was 68). Coverage includes:
  - test_schemas.py (32 tests for VN type parsers + SchemaResolver)
  - test_llm.py (22 tests for Ollama adapter, stub providers, Extract)
  - test_pipeline.py (35 tests across all 6 stages + composition)

### Dep changes
- `pydantic>=2.5` is now a hard dep (was optional `[doc]`). Required by
  `nom.doc.schemas`. Apache-licensed core (Rust) — small, audited, fast.
- `httpx>=0.27` and `pdfplumber>=0.11` added to `[dev]` so tests exercise
  the real Ollama and Parse paths. End users still install via `[llm]`
  / `[doc]` extras as before.

### Planned for v0.0.3
- **Study underthesea to build a better tokenizer in-tree.** underthesea
  (Apache 2.0) is the de-facto VN tokenizer and we reach ~78% boundary
  agreement at ~21× their throughput with a pure-rule approach. v0.0.3
  starts the work to close the accuracy gap *while keeping* the
  zero-dep / pure-Python / fully-auditable property:
    - Read the underthesea CRF feature templates (Apache 2.0 source)
    - Build our own training corpus from CC-BY-SA Vietnamese Wikipedia
      and ODC-BY mC4-vi
    - Train a small CRF (or distilled char-level Transformer) and ship
      the weights as part of nom-vn (with checksums and a public
      training script — no opaque blobs)
    - Run the same comparison bench; release v0.0.3 when we beat
      underthesea on agreement at our throughput
- **Diacritic ML backend.** v0.0.2 deferred this honestly. We evaluated PyVi
  (MIT, but crashes on `"duoc"` and bundles `.pkl` files) and HuggingFace
  DistilBERT-Viet (Apache 2.0, ~90%+ accuracy but ~1GB install weight).
  v0.0.3 picks: ship the DistilBERT-Viet wrapper as `[diacritics]` extras,
  or train our own lighter model alongside the tokenizer work above.
- Add `nom.text.is_diacritic_correct()` to detect misplaced tone marks.
- Expanded eval corpus (~500 sentences) drawn from CC-BY-SA Vietnamese
  Wikipedia samples + ODC-BY mC4-vi.

### Planned for v0.1.0
- `nom.doc.extract()` — real implementation: `pdfplumber`/`pymupdf` for PDFs,
  `pytesseract` for scans, schema-driven LLM extraction.
- `nom.llm.Ollama`, `nom.llm.OpenAI`, `nom.llm.Anthropic` adapters wired up.
- Built-in schemas: `Contract`, `OfficialDoc`, `Receipt`, `IDCard`.

### Planned for v0.2.0
- `nom.prompts.contracts`, `nom.prompts.gov_docs` — versioned prompt library.

## [0.0.2] — 2026-04-25

### Added
- `nom.text.word_tokenize` — **pure-Python** Vietnamese word segmentation
  with greedy compound-word merging (~300-entry curated table in
  `src/nom/text/_compounds.py`). Zero third-party deps. **77.77% boundary
  agreement with underthesea (CRF) at ~21× the throughput** (734k vs 34k
  tok/s, warmup + best-of-5), measured on
  `benchmarks/data/diacritic_eval_v0.txt`. Baseline JSON committed at
  `benchmarks/results/baseline_segment_v0.0.2.json`.
- `nom.text.sent_tokenize` — pure-Python sentence splitting with VN
  abbreviation awareness (e.g. doesn't split at `TP. Hồ Chí Minh`).
- `nom.text.text_normalize` — VN-aware whitespace + punctuation cleanup
  (distinct from Unicode-NFC `nom.text.normalize`).
- `benchmarks/accuracy/bench_segment.py` — comparison harness measuring our
  rule-based tokenizer against underthesea when installed.
- 23 new tests (`tests/test_segment.py`) covering tokenization, compound
  merging, sentence splitting, abbreviation handling, and text normalization.
- Optional dependency group `pip install nom-vn[nlp]` for users who want
  underthesea (Apache 2.0, ~80% reported VN segmentation accuracy) — used
  as a comparison reference in our benchmark, not a runtime requirement.

### Security notes (audited 2026-04-25)
- **PyVi rejected** on two counts: (1) bundles 4 `.pkl` files (Python pickle
  = arbitrary code execution on import), and (2) raises `KeyError: 'dr'` on
  the common token `"duoc"`. Not shippable.
- **underthesea accepted as optional dep**: ships CRFsuite native binary
  models (`lCRF...` magic header), which are deterministic-deserialized and
  do not execute arbitrary code. License is Apache 2.0 (compatible). We
  attribute upstream in `pyproject.toml`.
- **Default path stays zero-dep**: the pure-Python `nom.text.word_tokenize`
  works without any extras installed. Users opt into underthesea explicitly.

### Changed
- Version bumped to 0.0.2 in `pyproject.toml` and `nom.__version__`.
- `pyproject.toml` `[diacritics]` group is now an empty placeholder for v0.0.3.

### Not changed
- `fix_diacritics` still uses the rule-based table — 41% baseline holds.
  ML backend deferred honestly to v0.0.3.

## [0.0.1] — 2026-04-25

Initial release. Working `nom.text` module; preview API for `nom.doc` and
`nom.llm`.

### Added
- `nom.text.normalize` — Unicode NFC normalization (9M ops/s).
- `nom.text.strip_diacritics` — ASCII-fold Vietnamese.
- `nom.text.has_diacritics` — boolean diacritic check.
- `nom.text.is_vietnamese` — heuristic detection (works on stripped text).
- `nom.text.fix_diacritics` — rule-based diacritic restoration on a curated
  business-vocabulary table (~120 high-frequency words).
- Preview API stubs for `nom.doc.extract` and `nom.llm.{Ollama, OpenAI, Anthropic}`.
- Test suite — 22 tests, all passing.
- Performance benchmark — `scripts/bench_text.py`.
- Component selection rationale + benchmark numbers — `docs/benchmark.md`.
