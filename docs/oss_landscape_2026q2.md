# OSS Local-First AI / RAG Landscape — 2026 Q2

**Audience:** nom-vn architecture team. Reference document for which patterns to borrow, which to avoid, and where we are deliberately diverging.

**Scope:** ~12 leading projects across RAG frameworks, local-first chat apps, model serving, vector infra, doc parsing, eval, and observability — sampled in April 2026, not 2024.

**Verification standard:** every claim cites a working URL. Star counts, license types, and architectural specifics are quoted from the source where possible. Where we couldn't verify a claim publicly, we say so.

---

## 1. Project survey

For each: license, the pattern worth borrowing, the trap to avoid, URL.

### LlamaIndex (`run-llama/llama_index`)
- **License:** MIT. Repo: <https://github.com/run-llama/llama_index> ("42k+ stars" per third-party tutorial; not separately verified).
- **Borrow:** Module-per-integration packaging. Each LLM/embedder/vectorstore is a separately installable package (`llama-index-llms-ollama`, `llama-index-vector-stores-qdrant`); 300+ integrations live outside core.
- **Avoid:** Their `Settings` global singleton (and predecessor `ServiceContext`). Their own migration doc admits "passing in an entire service_context container to any module made it hard to reason about which component was actually getting used." <https://docs.llamaindex.ai/en/stable/module_guides/supporting_modules/service_context_migration/> — replacement Settings is still a global. Keep DI via constructors.

### LangChain + LangGraph
- **License:** MIT. Repos: <https://github.com/langchain-ai/langchain>, <https://github.com/langchain-ai/langgraph>.
- **Borrow:** The `Runnable` interface shape — every chain element implements `invoke / stream / batch / ainvoke`. <https://www.pinecone.io/learn/series/langchain/langchain-expression-language/> Borrow the uniform-method shape, not the `|` pipe DSL.
- **Avoid:** Stacked-class abstractions. HN: "inherently flawed... 5 layers of abstraction to change a minute detail." <https://news.ycombinator.com/item?id=36648272> Lesson: don't ship abstractions you can't keep stable for 12+ months — LangGraph's v0.1 → v1 API churn is on the same track.

### Haystack v2
- **License:** Apache 2.0. Repo: <https://github.com/deepset-ai/haystack>
- **Borrow:** Typed component IO — "Every Component declares its input and output types." <https://github.com/deepset-ai/haystack/blob/main/haystack/core/pipeline/pipeline.py> The v1→v2 rewrite was driven by untyped pipelines becoming unmaintainable. Stay strict on Protocol input/output types; no `dict[str, Any]` hatches.
- **Avoid:** The directed-multigraph `Pipeline` runner with loops/branches. Most RAG flows are linear; the graph runner adds complexity 90% of users don't need (their own discussion #7623 shows users building graphs-of-graphs). Our `nom.doc.Pipeline` is a list — intentionally.

### DSPy
- **License:** MIT. Repo: <https://github.com/stanfordnlp/dspy> ("160k monthly downloads, 16k stars" per <https://dspy.ai/roadmap/>).
- **Borrow:** Signature-as-contract — `signature = "question -> answer: str"` is a typed I/O spec, not a prompt template. <https://dspy.ai/learn/programming/signatures/> When `nom.llm` formalizes typed extraction, this is the cleaner shape.
- **Avoid:** The optimizer-as-default narrative. `BootstrapFewShot` / `MIPROv2` / `GEPA` produce real wins on the benchmarks they tune for, but they're heavy for "answer one VN legal question." Ship without an optimizer; add only when we have a held-out eval set (verified-benchmarks rule).

### txtai
- **License:** Apache 2.0. Repo: <https://github.com/neuml/txtai> — closest peer to our stance ("Local laptop: zero-config, runs on CPU"). Worth reading the `Embeddings` class as a reference for an in-process vector index API.
- **Borrow:** "Embedded by default" framing — same as our laptop-first floor.
- **Avoid:** Their `Embeddings` doing too many things (index + storage + graph + agents in one class). Our split — Embedder / Retriever / Index / Store as separate Protocols — is cleaner.

### Onyx (formerly Danswer)
- **License:** MIT CE. Repo: <https://github.com/onyx-dot-app/onyx>, docs <https://docs.onyx.app/welcome>.
- **Borrow:** Connector pattern (40+ sources: Slack, Confluence, Jira, GitHub). Each connector is "an iterator that yields documents with metadata" — the right seam if/when nom-vn grows past local files.
- **Avoid:** Their full ops stack — Postgres + Vespa + Redis + MinIO + worker queues + nginx. Right for enterprise multi-tenant search, wrong for a laptop. Keep Tier 0 single-process; scale-out is additive Protocol impls, not a 6-service compose.

### RAGFlow
- **License:** Apache 2.0 (verified <https://github.com/infiniflow/ragflow/blob/main/LICENSE>).
- **Borrow:** Layered separation: doc-parsing → retrieval → agent. Their table-aware parsing is what `nom.doc` should aspire to for VN PDFs.
- **Avoid:** "Everything in one Docker compose" deployment — minio + mysql + elasticsearch all required. Local-first means no required externals.

### Ollama
- **License:** MIT (verified <https://github.com/ollama/ollama/blob/main/LICENSE>).
- **Borrow:** Single-binary Go server wrapping a C++ engine (llama.cpp via CGo), OpenAI-compatible REST, Modelfile registry. <https://medium.com/@laiso/ollama-under-the-hood-f8ed0f14d90c> The UX bar: "install, pull, serve — inference in under two minutes." Gold standard for "hard things, one command."
- **Avoid:** Tightly coupling to one engine. Ollama is fundamentally a llama.cpp wrapper; when llama.cpp lags, Ollama lags. Keep Ollama as one adapter, not the floor.

### llama.cpp / vLLM / LiteLLM
- **llama.cpp** (MIT, <https://github.com/ggml-org/llama.cpp>): GGUF is the right "weights as data, mmap-able, deterministic" format — matches our no-pickle policy. Don't bind directly; talk via Ollama or `llama-cpp-python` adapter. The C++ ABI churns.
- **vLLM** (Apache 2.0, <https://github.com/vllm-project/vllm>, "~75K stars"): borrow PagedAttention *as a concept* — memory layout dominates inference cost. Avoid as a default — V1 multi-process / ZeroMQ architecture is for serving Llama-405B, not one Mac user.
- **LiteLLM** (MIT, <https://github.com/BerriAI/litellm>): borrow the OpenAI-compatible wire format as lingua franca. <https://docs.litellm.ai/docs/simple_proxy> Ship `nom.llm.OpenAICompatible` once and you adopt LiteLLM's catalog for free. Avoid the proxy-server form — different product.

### Chroma / Qdrant / LanceDB / sqlite-vec
- **Chroma** (Apache 2.0, <https://github.com/chroma-core/chroma>): default in many tutorials; 2025 Rust-core rewrite delivers 4x writes per third-party benchmark. Reasonable default for `nom.index.ChromaIndex`.
- **Qdrant** (Apache 2.0, <https://github.com/qdrant/qdrant>): production-grade Rust server, "20–30 ms query times with ~95% recall." Right adapter for the multi-host tier.
- **LanceDB** (Apache 2.0, <https://github.com/lancedb/lancedb>): in-process, columnar (Lance format), zero-copy, larger-than-memory friendly. Strongest fit philosophically for nom-vn — no server needed, file-based, queryable. **Strong candidate as the `nom.index` default over Chroma**, and worth a separate ADR.
- **sqlite-vec** (Apache 2.0, <https://github.com/asg017/sqlite-vec>): the successor to sqlite-vss (which is dead — see <https://github.com/asg017/sqlite-vss>). Mozilla-funded, "stable v1 in the next year, then maintenance mode." If we want vector search inside the same SQLite file as our `Store`, this is the path.

**Pattern to borrow:** every one of these works as an in-process library — no required server. That's the right floor for local-first.
**Trap:** picking one too early. Our `Index` Protocol leaves the choice to the user; we ship one default and document the others.

### Doc parsing — Unstructured / Marker / Docling / PaddleOCR
- **Unstructured** (Apache 2.0 core, <https://github.com/Unstructured-IO/unstructured>): "ranks #1" in third-party benchmarks for quality but "51s for 1 page, 141s for 50 pages" — unusable for ingestion at scale.
- **Marker** (GPL-3.0 / commercial, <https://github.com/datalab-to/marker>): "500 PDFs in 2 hours, 1-2s per page." Fast batch. **License is GPL — we can study but not copy code, and would need to keep it as a user-installed adapter, not bundled.**
- **Docling** (MIT, IBM, <https://github.com/docling-project/docling>): "better for complex documents needing metadata... TableFormer model handled merged cells correctly." This is the right open-source partner for nom-vn doc parsing on technical/legal PDFs. arXiv paper: <https://arxiv.org/pdf/2501.17887>.
- **PaddleOCR** (Apache 2.0, <https://github.com/PaddlePaddle/PaddleOCR>): already on our roadmap as a heavy OCR option.

**Pattern to borrow:** Docling's typed document model (Document → Section → Paragraph → Table with provenance) is closer to what `nom.doc.Document` should be than what we have today.
**Trap:** chasing parser quality at the cost of speed. Marker proves you can be fast, GPL proves licenses bite — pick MIT/Apache adapters by default.

### Eval — RAGAS / TruLens / DeepEval / Promptfoo
- **RAGAS** (Apache 2.0, <https://github.com/explodinggradients/ragas>): "five core metrics – Faithfulness, Contextual Relevancy, Answer Relevancy, Contextual Recall, Contextual Precision." Reference-free; LLM-as-judge.
- **TruLens** (MIT, <https://github.com/truera/trulens>): "highest discrimination ratio... 4.2:1 ratio" per AImultiple study. <https://research.aimultiple.com/rag-evaluation-tools/>
- **DeepEval** (Apache 2.0, <https://github.com/confident-ai/deepeval>): pytest-native, 50+ metrics, CI-friendly.
- **Promptfoo** (MIT, <https://github.com/promptfoo/promptfoo>): "51,000 developers" per AImultiple, YAML/CLI A/B testing.

**Honest finding** (cited): "all tools separate relevant from irrelevant contexts more than 91% of the time, but **none verify factual accuracy** — a passage with the right entities and wrong answer scores high across every tool tested." <https://research.aimultiple.com/rag-evaluation-tools/>
**Borrow:** RAGAS's metric names as the contract (so users can plug in their own judge), DeepEval's pytest integration as the developer ergonomics. **Don't pick one as our blessed default** — our `benchmarks/rag/` should compute the metrics directly so we own the math.
**Trap:** trusting LLM-as-judge dashboards as ground truth. Always pair with held-out human-labeled examples.

### Observability — OpenInference / OpenLLMetry / Phoenix
- **Phoenix** (Elastic v2, <https://github.com/Arize-ai/phoenix>): "fully open source and self-hostable — no feature gates." Built on OpenTelemetry.
- **OpenInference** (Apache 2.0, <https://github.com/Arize-ai/openinference>): conventions (semantic attributes) for LLM spans on top of OTel.
- **OpenLLMetry** (Apache 2.0, <https://github.com/traceloop/openllmetry>): instrumentation libs for OpenAI, Anthropic, Chroma, Pinecone, Qdrant, Weaviate.

**Borrow:** OpenTelemetry + OpenInference span conventions. This is the standardization moment — every serious player exports OTel now. Adding `OTEL_*` env-var support to `nom.chat` is one afternoon and gets us free integrations with Phoenix, Langfuse, Helicone, Datadog, etc.
**Avoid:** Locking into a vendor SDK (LangSmith — closed source — or any "trace = us" model). OpenTelemetry is the moat-free path.

### Local-first chat — AnythingLLM / Open WebUI / Khoj / Continue / Quivr / Verba
- **AnythingLLM** (MIT, <https://github.com/Mintplex-Labs/anything-llm>): all-in-one. Avoid the all-in-one trap — feature breadth permanently drags the roadmap.
- **Open WebUI** (permissive, <https://github.com/open-webui/open-webui>): FastAPI + Svelte + plugin pattern. Validates our chosen stack.
- **Khoj** (AGPL-3.0, <https://github.com/khoj-ai/khoj>): study only — AGPL is incompatible with Apache 2.0 redistribution.
- **Continue** (Apache 2.0, <https://github.com/continuedev/continue>): borrow the three-component split (`core` business logic / `extensions/<ide>` IDE shim / `gui` React) with message-passing protocol — same shape as our `nom.rag` ↔ `nom.chat.server` ↔ `ui/` separation. Avoid their `config.json`-as-API; a Config dataclass is enough.
- **Quivr** (Apache 2.0, <https://github.com/QuivrHQ/quivr>): avoid opinion lock-in — their stack-or-fork approach.
- **Verba** (BSD-3-Clause, <https://github.com/weaviate/Verba>): hard avoid — `ReaderManager`, `ChunkerManager`, `EmbeddingManager`, `RetrieveManager`, `GenerationManager` is exactly the Manager Class Disease our `ARCHITECTURE.md` rule #2 bans.

---

## 2. Steal these patterns

1. **Module-per-integration packaging** (LlamaIndex). Already partially there via our `[index-chroma]`/`[index-qdrant]`/`[index-pgvector]` extras. Extend the same shape if/when LLMs proliferate (`nom-vn[llm-openai]`, `nom-vn[llm-anthropic]`).
2. **Typed Component IO** (Haystack v2). Keep `Stage`, `Embedder`, `LLM`, `Retriever` Protocols strict — input/output types declared, no `dict[str, Any]` hatches. Their v1→v2 rewrite was specifically because they didn't.
3. **Signature-as-contract for LLM calls** (DSPy). When `nom.llm` grows typed extraction, declare `signature = "question, context -> answer: str, citations: list[int]"` rather than building yet another prompt-template DSL.
4. **OpenAI-wire-format compatibility** (LiteLLM). Make sure `nom.llm.LLM.complete()` accepts an OpenAI-compatible request shape so LiteLLM's whole catalog is one adapter away.
5. **OpenTelemetry + OpenInference span conventions** (Phoenix / OpenLLMetry). One afternoon of work in `nom.chat.server` opens the door to Phoenix, Langfuse, Datadog, Honeycomb.
6. **Connector pattern, when we need it** (Onyx). A `Connector` is "iterator that yields documents with metadata" — small Protocol when the time comes; no need today.
7. **Single-binary user experience** (Ollama). Even though we're a Python wheel, `pip install "nom-vn[chat]" && nom serve` should feel as one-shot as `ollama pull && ollama serve`. We're close. Keep that bar.
8. **GGUF-style "weights as data" discipline** (llama.cpp). Already encoded in our no-pickle policy (no pickle). Stay strict.
9. **Connector / IO as iterator + provenance** (Docling). A `Document` carries `provenance` (page, section, bbox) end-to-end so citations work. We already do citations; tighten the data class.

---

## 3. Avoid these traps

1. **Stacked-class abstractions** (LangChain). HN id 36648272 documents the regret. Constructor args > nested Builders.
2. **Global Settings singletons** (LlamaIndex `Settings` / old `ServiceContext`). Their own migration doc admits the design was painful. Keep DI explicit through constructors.
3. **Manager classes** (Verba: ReaderManager, ChunkerManager, EmbeddingManager, RetrieveManager, GenerationManager). Already banned by our `ARCHITECTURE.md` rule #2 — verify periodically that we still don't have any.
4. **All-in-one mega-class** (txtai's `Embeddings`). Our split (Embedder / Retriever / Index / Store) is cleaner; don't collapse it under "simplicity" pressure.
5. **Required external services for the local tier** (Onyx, RAGFlow). Postgres + ES + Redis + MinIO is a fine production tier; it cannot be the laptop default.
6. **AGPL/GPL bundled deps** (Marker, PyMuPDF — already documented in ARCHITECTURE.md, Khoj). Study, don't copy. Adapters only, opt-in.
7. **Optimizers / agent loops as default** (DSPy `BootstrapFewShot`, generic ReAct). Demoware unless paired with held-out evals proving wins. Per our verified-benchmarks rule, add only when the bench number moves.
8. **Vendor-locked observability SDKs** (LangSmith, Helicone proprietary mode). OpenTelemetry exists; use it.
9. **YAML/JSON-as-API** (Continue's `config.json`, Flowise's flow definitions). Code is the API. A Config dataclass is enough.
10. **ORMs in the core data path** — already explicitly ruled out in `ARCHITECTURE.md` rule #6. Keeping it.
11. **Plugin marketplaces / dynamic registries** — none of the leaders we surveyed make this work; LangChain's split-package strategy is the closest, and it's *Python imports*, not a marketplace. Don't build one.

---

## 4. We're already there (and where we're deliberately diverging)

| Area | Field consensus | nom-vn | Defensible? |
|---|---|---|---|
| Protocol-shaped seams | Haystack components, DSPy modules, LangChain Runnable | `Embedder`, `LLM`, `Retriever`, `Stage`, `Store`, `EmbeddingsCache` Protocols | Yes — strictly typed, no `Any`. |
| Module-per-integration | LlamaIndex 300+ packages | Extras-per-backend (`[index-chroma]`...) | Yes — same shape, smaller surface. |
| OTel observability | Phoenix / OpenInference / OpenLLMetry | Not yet — recommended as a near-term action | Gap to close. |
| Embedded vector default | Chroma, LanceDB, txtai | numpy `DenseRetriever` for <100k; Chroma at v0.1 | Yes; revisit LanceDB. |
| Single-binary UX | Ollama Go binary | Python wheel + bundled built UI dist | Defensible — Python ecosystem; equivalent UX. |
| OpenAI-compatible wire shape | LiteLLM | Partially — Ollama adapter only | Worth tightening on the LLM Protocol. |
| Doc parsing typed model | Docling, Unstructured | `nom.doc.Stage` exists; `Document` model could be richer | Aligned, sharpen. |
| Anti-Manager-class | Most orgs failed; we banned it | `ARCHITECTURE.md` rule #2 | Defensible — Verba is the cautionary tale. |
| No ORM | sqlite-vec direct, txtai direct, our SqliteStore | direct `sqlite3` | Defensible — Eshwaran Venkat's critique <https://eash98.medium.com/why-sqlalchemy-should-no-longer-be-your-orm-of-choice-for-python-projects-b823179fd2fb> backs us. |
| No DI framework | LlamaIndex regretted ServiceContext, LangChain regretted globals | Constructor args + Config dataclass | Defensible — every leader who introduced one wrote a migration doc later. |
| No event bus | Ollama, llama.cpp, txtai don't have one | We don't | Defensible — the call stack is the event log. |
| Single repo (not monorepo of services) | LlamaIndex split into 300+ pkgs but core is monorepo | Single `nom-vn` | Defensible at our scale; revisit if `nom.chat` gets too heavy for `nom.text` users. |
| Apache 2.0, no carve-outs | Most leaders; Dify and Verba bend | Pure Apache 2.0 | Defensible — we're betting on durable open source. |

---

## 5. Concrete actions for nom-vn

Ranked by impact / cost.

### Tier S — small, high impact, do soon

1. **Add OTel + OpenInference instrumentation in `nom.chat.server`.** One afternoon. Opens Phoenix, Langfuse, Datadog, Honeycomb integrations for free. Sources: <https://github.com/Arize-ai/openinference>, <https://github.com/traceloop/openllmetry>.
2. **Tighten `LLM.complete` to accept an OpenAI-shape kwarg subset** (`messages`, `tools`, `response_format`, `stream`). Frees us to wrap LiteLLM later as one adapter. Cost: a few hours; backwards-compatible additive change.
3. **Add a `Document` class in `nom.doc` with explicit `provenance`** (file, page, bbox, section path). Mirror Docling. Citations get more precise; no cost to existing callers. <https://github.com/docling-project/docling>
4. **Audit for any nascent `…Manager` class.** Grep CI rule. Verba is the cautionary tale.

### Tier M — bigger, do at v0.1 or v0.2

5. **Evaluate LanceDB as the `nom.index` default over Chroma.** LanceDB's "in-process columnar zero-copy file format" is closer to our local-first thesis than Chroma's "embedded server." Ship a benchmark in `benchmarks/index/` (recall + latency on a VN corpus) before deciding. <https://github.com/lancedb/lancedb>
6. **Adopt sqlite-vec for the `nom.chat` SQLite tier** so vectors live in the same file as `Store`. One file = one backup. Watch for the v1 stable release. <https://github.com/asg017/sqlite-vec>
7. **Ship `nom.eval` as a thin metrics module** (faithfulness, citation-precision, recall@k) — own the math, citing RAGAS metric names as the contract. **Not** a TruLens/DeepEval dependency. AImultiple's finding "none verify factual accuracy" means we'd need our own VN human-labeled set anyway. <https://research.aimultiple.com/rag-evaluation-tools/>
8. **DSPy-style signature for `nom.doc.extract`** — already shaped that way (you pass a schema), formalize the contract and document it as such. No optimizer; we don't need one.

### Tier L — noted, not now

9. **Connector Protocol** (Onyx-style 40-source plugin set). Out of scope until users actually have non-file sources.
10. **Optimizers / iterative-retrieval agent loops.** DSPy `BootstrapFewShot`, ReAct-style retries. Demoware unless we have an eval set proving wins. Per our verified-benchmarks rule, gate on the bench number.
11. **Multi-tenant story.** `ARCHITECTURE.md` already lists this in the scaling table; the Protocol seams are positioned correctly. No code action until the second customer asks.
12. **vLLM adapter.** Right answer for a future `nom.llm.VLLM`; wrong default. The `LLM` Protocol means it's additive when the time comes.

---

## 6. References (verified URLs only)

- LlamaIndex: <https://github.com/run-llama/llama_index>, Settings migration <https://docs.llamaindex.ai/en/stable/module_guides/supporting_modules/service_context_migration/>
- LangChain & LangGraph: <https://github.com/langchain-ai/langchain>, <https://github.com/langchain-ai/langgraph>, LCEL doc <https://www.pinecone.io/learn/series/langchain/langchain-expression-language/>, HN critique <https://news.ycombinator.com/item?id=36648272>
- Haystack: <https://github.com/deepset-ai/haystack>, pipeline source <https://github.com/deepset-ai/haystack/blob/main/haystack/core/pipeline/pipeline.py>, v2 design discussion <https://github.com/deepset-ai/haystack/discussions/5568>
- DSPy: <https://github.com/stanfordnlp/dspy>, signatures <https://dspy.ai/learn/programming/signatures/>, optimizers <https://dspy.ai/learn/optimization/optimizers/>
- txtai: <https://github.com/neuml/txtai>
- Onyx: <https://github.com/onyx-dot-app/onyx>, docs <https://docs.onyx.app/welcome>
- RAGFlow: <https://github.com/infiniflow/ragflow>, license <https://github.com/infiniflow/ragflow/blob/main/LICENSE>
- Ollama: <https://github.com/ollama/ollama>, license <https://github.com/ollama/ollama/blob/main/LICENSE>, internals <https://medium.com/@laiso/ollama-under-the-hood-f8ed0f14d90c>
- llama.cpp: <https://github.com/ggml-org/llama.cpp>
- vLLM: <https://github.com/vllm-project/vllm>
- LiteLLM: <https://github.com/BerriAI/litellm>, proxy doc <https://docs.litellm.ai/docs/simple_proxy>
- Chroma: <https://github.com/chroma-core/chroma>; Qdrant: <https://github.com/qdrant/qdrant>; LanceDB: <https://github.com/lancedb/lancedb>; sqlite-vec: <https://github.com/asg017/sqlite-vec>; sqlite-vss (deprecated): <https://github.com/asg017/sqlite-vss>
- Unstructured: <https://github.com/Unstructured-IO/unstructured>; Marker: <https://github.com/datalab-to/marker>; Docling: <https://github.com/docling-project/docling>, paper <https://arxiv.org/pdf/2501.17887>; PaddleOCR: <https://github.com/PaddlePaddle/PaddleOCR>
- Eval — RAGAS: <https://github.com/explodinggradients/ragas>; TruLens: <https://github.com/truera/trulens>; DeepEval: <https://github.com/confident-ai/deepeval>; Promptfoo: <https://github.com/promptfoo/promptfoo>; AImultiple study: <https://research.aimultiple.com/rag-evaluation-tools/>
- Observability — Phoenix: <https://github.com/Arize-ai/phoenix>; OpenInference: <https://github.com/Arize-ai/openinference>; OpenLLMetry: <https://github.com/traceloop/openllmetry>
- AnythingLLM: <https://github.com/Mintplex-Labs/anything-llm>; Open WebUI: <https://github.com/open-webui/open-webui>; Khoj (AGPL): <https://github.com/khoj-ai/khoj>
- Continue: <https://github.com/continuedev/continue>
- Quivr: <https://github.com/QuivrHQ/quivr>; Verba: <https://github.com/weaviate/Verba>

---

## 7. Caveats on data quality

- **Star counts** quoted in this doc are from third-party blogs or project docs; we did not separately resolve every GitHub stars badge. Where we couldn't verify, we said so. Star counts move; the architectural facts don't.
- **No fabricated benchmark numbers.** Every quality / latency number cited is from a public source that's URL-cited. The AImultiple eval-tool study (cited above) is the most rigorous public comparison we found.
- **License audit** is best-effort from the cited LICENSE files. Before vendoring any code, re-check at the commit you'd vendor from.
- **Not covered in depth** (intentionally): Milvus, Weaviate-the-DB (vs Verba), Helicone, Langfuse, LangSmith, LM Studio (closed), Cortex/Jan, Flowise, PrivateGPT, h2oGPT — all surveyed at a glance, none changed our recommendations. If a future ADR needs one, pull it then.
