# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Component selection rationale + benchmark numbers — `docs/BENCHMARK.md`.
