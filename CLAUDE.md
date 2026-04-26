# CLAUDE.md — nom-vn project notes for AI assistants

This file is auto-loaded by Claude Code when working inside `nom-vn/`. It points
to durable project context. For the broader Atlas operating manual see the
parent `PPlanning/CLAUDE.md`.

## Vietnamese benchmark datasets

Test corpora live under [`benchmarks/data/`](benchmarks/data/). The full
catalogue, license notes, and intended-use map are in
[`docs/datasets.md`](docs/datasets.md).

When you need Vietnamese text, PDF, or image fixtures for tests or benchmarks,
prefer these over hand-curating new examples:

- **Sentences (4 registers)** → `benchmarks/data/diacritic_eval_v0.txt` (CC0)
- **Declarative prose** → `benchmarks/data/udhr_vi/` (CC-BY-SA / PD)
- **Classical literary** → `benchmarks/data/wikisource_vi/` (PD content)
- **Encyclopedia long-form** → `benchmarks/data/wiki_vi/articles.jsonl` (CC-BY-SA)
- **Conversational sentences** → `benchmarks/data/tatoeba_vi/` (CC-BY)
- **Born-digital PDF** → `benchmarks/data/udhr_vi/udhr_vie.pdf` (PD)
- **OCR images (with ground truth)** → `benchmarks/data/synthetic_ocr_vi/` (CC0)
- **Vietnamese legal / governance** → `benchmarks/data/legal_vi/` (PD per Luật SHTT §15)
- **Synthetic Office (DOCX/XLSX/PPTX)** → `benchmarks/data/office_vi/` (PD, generator-built)

All datasets are regeneratable via:

```bash
python benchmarks/data/_fetch_all.py
python benchmarks/data/synthetic_ocr_vi/render.py
```

When adding a new dataset, follow the rules in `benchmarks/data/README.md` and
update `docs/datasets.md` so the catalogue stays current.

## Component build workflow — real models, real data, VN-specific research

When building or refining any pipeline component (retriever, reranker, embedder,
chunker, parser, generator), follow this loop. Skipping stages produces brittle
or untruthful results.

1. **Research the lightweight VN-specific options first.** Survey Hugging Face
   and recent papers (2024-2026) for the smallest open-source model that gets
   close to SOTA on Vietnamese. Record license, file format, reported VN
   benchmark numbers from a public source, and base architecture.
   General-multilingual baselines (BGE, mE5, Qwen3) are valid candidates but
   prefer VN-finetuned variants when license + audit pass and the gap is
   measurable. Document the survey in
   `research/<YYYY-MM-DD>-<topic>/report.md` or the relevant
   `docs/sota_*` page with citations.

   **File-format trust ladder** (refines parent CLAUDE.md principle 11):

   | Format | Status | Why |
   |---|---|---|
   | `safetensors` | ✅ **always preferred** | Deterministic, zero code execution on load. |
   | HF `.bin` / `pytorch_model.bin` | ⚠️ acceptable from a major lab when no safetensors variant exists | These are pickled too, *but* they're audited at scale and downloaded with a SHA256 checksum from a known-trusted host (HuggingFace Hub). Bias: prefer the safetensors revision when both exist (most BAAI / Meta / Google / Mistral / Qwen models now ship both). When only `.bin` is offered (older models, some research repos), accept *only* if the publisher is a major institution with reproducible weights. Document the choice in the model wrapper docstring with a one-line "no safetensors variant published — trusting HF SHA256 + publisher" note. |
   | `.pkl` / `.pickle` | ❌ **auto-reject regardless of source** | Same RCE surface as `.bin`, but without the HF checksum infrastructure or publisher accountability. We caught PyVi shipping these in v0.1 — never again. |
   | Opaque native binaries (CRFsuite `lCRF…`, etc.) | ⚠️ acceptable when license + format are documented and the format spec is public | Deterministic but opaque. Prefer in-tree reimplementation if accuracy gap is small. |

   The parent rule "prefer in-tree reimplementation when feasible" still
   applies — but it's a tradeoff, not an absolute. Reimplementing a
   1B-param transformer is not feasible; reimplementing a 5kb CRF
   tokenizer is.
2. **Build the smallest dependency surface that meets the quality goal.** Lazy
   imports, Protocol seams, frozen dataclasses on hot paths.
3. **Test with real models, not just fakes.** Unit tests use fakes for speed —
   that's correct. But before claiming a feature ships, write at least one
   integration test or benchmark run against the actual model the user will
   download (`pytest -k integration` or `python benchmarks/.../bench_*.py
   --embedder vietnamese --reranker BAAI/bge-reranker-v2-m3`). Skip-on-import
   patterns are fine for CI environments without the model cache.
4. **Benchmark on real Vietnamese datasets, not toy fixtures.** Tiny synthetic
   fixtures are useful for harness validation but cannot show component value
   when every retriever scores 1.000. Pull from a real public VN corpus
   (Zalo Legal QA mirror, ViQuAD, MIRACL-vi, or a Wikipedia sample of similar
   size). Commit a baseline JSON under `benchmarks/.../baselines/` so the next
   change re-measures cleanly.
5. **Iterate components and pipelines as a grid, not one at a time.** Try
   each candidate model under the same fixture, same metrics, same warmup +
   best-of-N protocol. Report the table with explicit `embedder`, `reranker`,
   `chunk_max_tokens`, etc., in the result JSON config block — silent
   defaults will desync from claims later.
6. **Honest empties beat fake numbers.** Quality cells without a
   committed-and-runnable bench script must be left empty / TBD per parent
   CLAUDE.md principle 12. Disclaimers like "preliminary" do not rescue
   fabricated metrics.
7. **Cross-check our numbers against the model's published benchmarks.** After
   running a real-model bench, find the model card / paper for each component
   and compare. If our number is materially different from the public number
   (say >10% relative on the same metric), **stop and investigate** before
   shipping or claiming. Common causes:
   - Different test corpus (ours is harder/easier or different register).
   - Wrong tokenization (model expects word-segmented input but we pass raw).
   - Wrong sequence length / truncation cap (model card says 512, we cap at
     256; or position-table off-by-one; see VietnameseEmbedder docstring for
     the XLM-RoBERTa quirk).
   - fp16/fp32 mismatch, wrong device (CPU vs GPU), missing normalization.
   - Cold-start artefacts (no warmup, lazy model load inflating first-pass
     latency — caught the 135× → 21× ratio incident on 2026-04-25).
   - Wrong metric variant (NDCG vs MAP, @10 vs @20, micro vs macro average).
   Either fix the issue and re-measure, or document the divergence honestly
   in `docs/benchmark.md` with the explanation. **Do not ship a number that
   silently disagrees with the upstream's published number** — readers will
   compare and lose trust.

## Autonomous improvement loop

When the user says any of: "continue until done", "don't stop", "improve until done",
"work as ML expert engineer until done", or any open-ended "keep improving" directive,
operate in autonomous mode:

1. **Build a checklist of concrete improvements** based on (a) the current state of
   benchmarks/results and docs/, (b) any tasks marked pending in the task system, and
   (c) the user's latest question or steering. Use TaskCreate to track each item.
2. **Decide the next item automatically.** Pick by ROI = (user-visible impact) /
   (engineering cost). If two items tie, prefer the one that closes a measurement
   gap (we shipped a recommendation without bench-data) over greenfield work.
3. **Execute. Don't ask for confirmation.** The user has already asked you to keep
   going. Asking "should I proceed?" between tasks wastes their attention.
4. **If genuinely blocked** (missing dependency, contradictory data, an external
   API down), research first — web search, HF Hub, GitHub issues, model cards.
   If after a single round of research you still can't decide, write a one-line
   summary of the blocker, mark the task pending with the reason, move to the next.
   Don't stop.
5. **Off-the-shelf before training.** Before recommending a fine-tune or distillation
   run, exhaustively bench public Apache/MIT/BSD/safetensors candidates on the
   exact same corpus you'd evaluate the trained model on. We caught one of these
   on 2026-04-26: a "distil a 100M-param VN diacritic model" recommendation was
   shipped without first benching `Toshiiiii1/Vietnamese_diacritics_restoration_5th`
   (Apache, safetensors, 200M) and similar. The user correctly flagged it.
6. **Each item ends in a commit.** No long-running uncommitted state. After each
   improvement: lint, run tests, commit with a focused message. Bump the patch
   version when the change is user-visible (new bench numbers, new dep, new API).
7. **Trust the trust ladder.** Per principle 11 + the file-format trust ladder in
   the component-build workflow: safetensors ≫ HF .bin from major labs ≫ opaque
   native ≫ pickle (auto-reject). When evaluating a new candidate model, the
   *first* check is the format / license, not the metric.

The aim of autonomous mode is sustained throughput, not "many small commits".
Skip work that doesn't move a measurable number; focus on the items that close
a real gap surfaced by the latest benches.

## Scope clarification

`nom-vn` is named after **chữ Nôm** (the historical Vietnamese script) but the
OCR target and processing pipeline are **modern Vietnamese in chữ Quốc Ngữ** —
Latin script with diacritics. Do not prioritize Hán-Nôm corpora or features
when scoping training data, benchmarks, or modules.

## Research and citations

Any document under `docs/research/` (and SOTA / landscape docs in `docs/`) must
back factual claims with verifiable citations:

- Inline links or numbered footnotes for every dataset size, license, benchmark
  number, and model detail.
- A "References" section at the end listing every URL.
- If a claim cannot be cited, write **"no published source"** or **"unverified"**
  explicitly. Do not guess.

This enforces CLAUDE.md principle 12 (verified benchmarks only) at the
documentation layer.

## Environment setup

One-time setup for a fresh clone:

```bash
# 1. Python (3.10+)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,chat,otel]"

# 2. Frontend (Node 20+ / pnpm 10+)
cd ui && pnpm install && cd ..

# 3. OCR (optional but recommended for image / scanned-PDF tests)
sudo apt install tesseract-ocr tesseract-ocr-vie       # Debian / Ubuntu
# OR
conda install -c conda-forge tesseract                 # cross-platform
brew install tesseract tesseract-lang                  # macOS

# 4. Pre-commit hooks
pre-commit install

# 5. Local LLM (Ollama for the chat web app)
ollama pull qwen3:8b   # default; or qwen3:1.7b for laptop / phi4 for headroom
```

Verify the install:

```bash
pytest                           # 250+ tests should pass
cd ui && pnpm typecheck && pnpm lint && pnpm build && cd ..
nom serve --in-memory            # then open http://localhost:8080
```

## Code style — Python

Hard rules. CI fails if any are violated.

- **Type-everywhere.** Public functions get full type annotations. Use
  `from __future__ import annotations` so forward references work cheaply.
  No `Any` in public APIs except for genuine duck-types (callbacks, dynamic
  config dicts) — comment why.
- **Protocols, not ABCs.** `typing.Protocol` (with `runtime_checkable`
  when `isinstance` checks help) for every swap point. See
  `nom.chat.Store` and `nom.chat.EmbeddingsCache` as references. ABCs
  are banned for shared behavior — use module-level helpers instead.
- **Frozen dataclasses for value objects.** `@dataclass(frozen=True, slots=True)`
  for hot-path immutables (`Citation`, `Hit`, `Chunk`).
- **No mutable default args.** `field(default_factory=list)`, never `= []`.
- **Local imports for heavy / optional deps.** numpy, torch,
  sentence-transformers, pdfplumber etc. import inside the function
  that needs them so `from nom import …` stays cheap. See
  `MemoryStore.ask` for the pattern.
- **Lint + format.** `ruff check .` and `ruff format --check .` must
  pass. Line length 100. Sort imports with isort (config in
  `pyproject.toml`).
- **Type check.** `mypy --strict src/` must pass. Files outside `src/`
  are excluded but should still be type-aware where it helps.
- **Comments.** Default to writing none. Add one when WHY is non-obvious
  (a workaround, a hidden invariant, a measured tradeoff). Never
  narrate WHAT the code does — well-named identifiers do that. See
  parent `PPlanning/CLAUDE.md` principles for the full rule.
- **No `…Manager` class names.** A pre-commit hook bans them — see
  `docs/architecture.md` anti-pattern rule #2 and the cited Verba
  example in `docs/oss_landscape_2026q2.md`.

## Code style — TypeScript / React (`ui/`)

- **Strict TS.** `strict`, `noUnusedLocals`, `noUnusedParameters`,
  `noFallthroughCasesInSwitch` all on. `any` lints to a warning;
  use `unknown` + narrow.
- **Prettier owns formatting.** 100-col, double quotes, semicolons,
  trailing commas. `pnpm format` to apply, `pnpm format:check` in CI.
- **ESLint flat config** with `typescript-eslint` strict + react-hooks.
  No console outside `console.warn` / `console.error`.
- **Functional components only.** No class components. State via
  `useState` / `useReducer`; data via TanStack Query.
- **No new global state libs.** Zustand / Redux / Jotai are off the
  table — TanStack Query handles server state, `useState` lifted to a
  parent handles client state. If that's painful, the component is too
  big.
- **Tailwind** for styling. Design tokens encoded in
  `ui/tailwind.config.ts` (cream `#f1ede3` / ink `#141414` / accent
  `#c46a37`). Sharp corners (no `border-radius`). Editorial palette is
  non-negotiable.
- **Radix primitives** copied into `ui/src/components/ui/` (the ShadCN
  pattern). Don't depend on `@shadcn/ui` as a runtime package.
- **No new bundle-bloating deps without measurement.** The current
  bundle is ~125 KB gzipped — keep it under 200 KB unless a feature
  earns the increase.

## Test rules

- **`pytest tests/` from repo root.** Excluding
  `test_pipeline.py::TestOCRStage` is acceptable when tesseract isn't
  installed.
- **Integration tests skip cleanly** when their optional deps are
  absent (use `pytest.importorskip` or `pytest.mark.skipif`). Don't
  gate the whole suite on a heavy dep.
- **No real LLM / embedder calls in unit tests.** Use the `_FakeLLM` /
  `_FakeEmbedder` doubles in `tests/test_chat.py` (or
  duplicate-into-test pattern). `tests/test_data_pipelines.py` is the
  integration tier and may use real models — mark it explicitly.
- **Multi-store coverage**: anything touching `Store` Protocol uses
  the `@pytest.fixture(params=["memory", "sqlite"])` pattern in
  `tests/test_multi_space.py`. Both impls must stay in lockstep.

## Pre-commit

```bash
pre-commit run --all-files
```

Runs: ruff (lint + format), mypy strict, codespell, markdownlint, the
ban-Manager-class-names check, and the ui-* hooks (prettier check,
eslint, tsc no-emit). All hooks must pass before merge — never use
`--no-verify` to bypass.

## Run / dev commands

| Goal | Command |
|---|---|
| Run the chat web app (persistent at `~/.nom`) | `nom serve` |
| Same, ephemeral / no disk | `nom serve --in-memory` |
| Same, custom port + model | `nom serve --port 9000 --model phi4` |
| Frontend dev with hot reload | `cd ui && pnpm dev` (proxies `/api` to localhost:8090) |
| Build the UI bundle for the wheel | `scripts/build_ui.sh` |
| Run tests | `pytest` |
| Run RAG retrieval bench | `python benchmarks/rag/bench_rag_vn.py` |
| Generate Office test fixtures | `python benchmarks/data/office_vi/_generate.py` |
| Seed a running server with demo spaces | `python scripts/seed_demo.py` |

## Other reading

- [`docs/architecture.md`](docs/architecture.md) — module map and design
- [`docs/pipeline.md`](docs/pipeline.md) — v0.1 doc-extraction pipeline
- [`docs/benchmark.md`](docs/benchmark.md) — measured numbers per module
- [`docs/sota_vn_2026q2.md`](docs/sota_vn_2026q2.md) — current LLM/embed/OCR picks
- [`docs/oss_landscape_2026q2.md`](docs/oss_landscape_2026q2.md) — OSS borrow / avoid analysis
- [`docs/research/`](docs/research/) — deeper research notes
- [`benchmarks/README.md`](benchmarks/README.md) — how to reproduce numbers
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — dev setup and PR rules
