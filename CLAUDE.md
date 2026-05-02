# CLAUDE.md — nom-vn AI assistant notes

Auto-loaded inside `nom-vn/`. Parent: `PPlanning/CLAUDE.md`.

## Scope

Named after chữ Nôm (historical) but targets **modern VN in chữ Quốc Ngữ**.
Don't prioritize Hán-Nôm corpora.

## Datasets

VN test corpora live in [`benchmarks/data/`](benchmarks/data/); catalogue in
[`docs/datasets.md`](docs/datasets.md). Prefer these over hand-curated text:

- Sentences (4 registers) → `diacritic_eval_v0.txt` (CC0)
- Declarative → `udhr_vi/` (PD) · Classical → `wikisource_vi/` (PD)
- Long-form → `wiki_vi/articles.jsonl` (CC-BY-SA)
- Conversational → `tatoeba_vi/` (CC-BY) · Born-digital PDF → `udhr_vi/udhr_vie.pdf`
- OCR images → `synthetic_ocr_vi/` (CC0) · Legal → `legal_vi/` (PD)
- Office docs → `office_vi/` (PD)

Regenerate: `python benchmarks/data/_fetch_all.py` and
`python benchmarks/data/synthetic_ocr_vi/render.py`.

## Component build workflow

For every new module / model integration, run all stages:

1. **Research.** Survey HF + 2024-26 papers for the smallest VN-finetuned
   open-source model. Record license, file format, public VN benchmark
   number, base arch. Document under `research/<YYYY-MM-DD>-<topic>/` or
   `docs/sota_*` with citations.
2. **Build.** Smallest dependency surface meeting the quality goal. Lazy
   imports, Protocol seams, frozen dataclasses on hot paths.
3. **Test with real models.** Unit tests use fakes; before claiming a
   feature ships, write at least one integration run against the actual
   downloadable model.
4. **Benchmark on real VN data.** Tiny synthetic fixtures show nothing
   when every retriever scores 1.000. Use Zalo Legal QA mirror, ViQuAD,
   MIRACL-vi, or a wiki sample. Commit a baseline JSON.
5. **Iterate as a grid.** Same fixture, same metrics, same warmup +
   best-of-N. Report config in result JSON (silent defaults desync from
   claims).
6. **Honest empties beat fake numbers** (parent §12).
7. **Cross-check vs the model's published number.** Differs >10 % rel on
   the same metric → stop and investigate. Common causes: register
   mismatch, wrong tokenization, wrong max_length, fp16/fp32, cold-start,
   wrong metric variant. Document divergence in `docs/benchmark.md`.

### File-format trust ladder

| Format | Status | Why |
|---|---|---|
| `safetensors` | ✅ always preferred | Deterministic, zero-RCE on load |
| HF `.bin` | ⚠️ accept from major lab when no safetensors exists | Pickled but HF Hub provides SHA256 + audited at scale; document the choice in the wrapper docstring |
| `.pkl` / `.pickle` | ❌ auto-reject | Same RCE without HF accountability (PyVi v0.1) |
| Opaque native (CRFsuite, …) | ⚠️ when format spec is public | Deterministic but opaque; prefer in-tree reimpl when accuracy gap is small |

Reimplement a 5kb CRF tokenizer; don't reimplement a 1B-param transformer.

## Autonomous improvement loop

When the user says "continue until done" / "don't stop" / "improve until
done" / open-ended "keep improving":

1. Build a checklist (TaskCreate) from current bench/doc state, pending
   tasks, latest user steering.
2. Decide next item by ROI = user-visible impact / engineering cost. Tie
   → prefer the one that closes a measurement gap.
3. Execute. Don't ask between tasks.
4. **Blocked?** Research first (web, HF Hub, GitHub issues, model cards).
   Still blocked after one round → one-line summary, mark pending, move
   on.
5. **Off-the-shelf before training.** Before recommending a fine-tune,
   exhaustively bench public Apache/MIT/BSD/safetensors candidates on
   the same corpus.
6. **Multi-corpus required for adoption claims.** Bench on ≥2 distinct
   registers. >10 pp spread → register-overfit; pick a
   register-conditional default.
7. Each item ends in a commit. No long-running uncommitted state.
8. **Always double-check before claiming a number:**
   - Implausible metric check (0 % / 100 % / sub-30 % when card says 90 %
     → bench bug).
   - Cross-reference upstream number (>10 % rel diff → investigate).
   - Dump 5 raw I/O samples and read them. (We caught a 0/800 metric bug
     this way 2026-04-26.)

## VN-language gotchas

### Encoding & normalization

- **NFC vs NFD.** "ề" (U+1EC1) ↔ "e" + combining marks. NFC-normalize
  before any compare. `nom.text.normalize` does this. **Audit every new
  training corpus** with `unicodedata.normalize('NFC', t) == t` on a
  sample. (`tmnam20/Vietnamese-News-dedup` is ~79 % NFD; v5 mixed-source
  training regressed -15.45 pp because of this. `has_diacritics` filter
  does NOT catch NFD because U+0111 'đ' is a distinct codepoint.)
- **đ has a stroke, not a diacritic** (U+0111). `strip_diacritics` must
  replace explicitly.
- **Stacked diacritics.** "ờ" = ơ + grave; multiple precomposed +
  decomposed forms exist. Don't roll your own normalizer.
- 6 vowel-modifiers × 5 tones × 2 modifiers ≈ 60 vowel forms.

### Tokenization & word boundaries

- VN spaces between syllables, not words. "thành phố Hồ Chí Minh" =
  1 word, 5 tokens.
- **bkai-vietnamese-bi-encoder needs underscored input.** "đường thủy" →
  "đường_thủy". Raw text drops R@1 by 15-20 pp. `BKaiEmbedder._segment`
  handles this — don't bypass.
- **`.split()` is wrong for measuring quality.** UD treebank ships
  spaces around punctuation; modern seq2seq attaches them. Always
  `normalize_punct()` both sides — see
  `benchmarks/accuracy/bench_diacritic_hf_udvtb.py`.
- Tokenizer choice: byte-level for typo tolerance, BPE for speed,
  SentencePiece for cross-lingual.

### Datasets — registers, traps

- **Register-shift is the #1 hidden quality failure.** A
  business/news-trained model collapses on classical-literary register
  and vice versa. Toshiiiii1 4-register matrix (2026-04-29): UDHR
  formal 98.14 % → business 97.81 % → conversational 93.77 % → literary
  89.40 %. 8.7 pp spread. ≥2 registers is the floor; 3-4 cornering
  distinct genres before adoption.
- **Trusted VN evals** (license + format + register):
  - `diacritic_eval_v0.txt` — 55 hand-curated, 4 registers, CC0
  - `UD_Vietnamese-VTB` test — 800 literary, gold word seg, CC-BY-SA-4.0
  - `Zalo Legal QA` (GreenNode) — 61k articles + 788 Q, MIT, legal
  - `udhr_vi.txt` — UN HR, 19 KB, formal, PD; slice via
    `build_diacritic_eval.py` (72 sentences)
  - `tatoeba_vi/vie_sentences_sample_3k.tsv` — 3k conversational,
    CC-BY 2.0 FR; slice (300 sentences)
- **Don't trust by default:** VLSP 2013 (gated), Surya OCR
  (license-incompatible), Vintern handwriting (license unclear).
- Reproduces: bkai 73.28 → 76.25 R@1 on Zalo Legal (tighter distractors).
  Did NOT reproduce: halong claimed 82.94, we measured 55.00.

### Metrics

- **Word accuracy ≠ diacritic recall.** "và", "của" no-op for
  restoration. Always also report **diacritic recall**.
- **Sentence-exact match** is brutal — one missed proper noun fails the
  whole sentence. Stress test, not headline.
- **CER** for OCR = Levenshtein over NFC chars. **Diacritic-CER** = CER
  on combining marks after NFD decompose (the failure VN readers feel
  most).
- **F1 for word seg** = on token spans (start, end), not strings.
- **Implausible metrics demand investigation.** 0 % / 100 % on a real
  model = bench bug.

### Model output traps

- **Qwen3 thinking mode** silently emits CoT to a separate `thinking`
  field on Ollama 0.21+, leaving `content` empty. Default
  `Ollama(think=False)`.
- **Generic LLMs ramble.** Use structured output (`{"restored": "..."}`
  JSON schema) on Ollama `format`.
- **VLM OCR hallucinates on tight line crops.** `qwen2.5vl:7b` got 31 %
  CER on clean printed VN lines (vs Tesseract 5 %). VLMs = right for
  *understanding* docs (forms, invoices, ID cards, handwriting); wrong
  for transcribing clean lines.
- **mE5 family expects `query:` / `passage:` prefixes.** Without them
  retrieval craters 15-25 pp. `bench_embedder_compare.py` auto-detects.
- **PhoBERT-base position table = 256, not 514.** Sending 512-cap trips
  an SDPA CUDA assert. `CrossEncoderReranker` auto-detects from
  `config.json`.

### Proper nouns

`Hung` → `Hùng` / `Hưng` / `Hứng`. `Le` → `Le` / `Lê` / `Lễ`. A
restoration model picks most-frequent in training data — that's not
always right. Most Toshiiiii1 UD-VTB errors are this class. Don't
declare "broken" because of disambiguation. When gold proper noun is
required (legal docs, forms), it's a separate **NER + lookup** problem.

## Research and citations (`docs/research/`, `docs/sota_*`)

Every factual claim → inline link or numbered footnote. References
section at end. Uncitable claim → write **"no published source"** /
**"unverified"** explicitly. Don't guess.

## Publishing to HF Hub (`nrl-ai/*`)

1. **Cite Viet-Anh Nguyen on every artifact** (parent §13). BibTeX:
   `author={Nguyen, Viet-Anh and {Neural Research Lab}}`. Apply
   retroactively when patching old cards.
2. **Verify after every push** (parent §14). `huggingface_hub.upload_*`
   success ≠ valid YAML.
   - `HfApi().model_info(repo_id)` / `dataset_info` and check
     `pipeline_tag`, `library_name`, `tags`, `siblings`.
   - For datasets: `datasets.load_dataset(repo_id, config)` to confirm
     each config parses.
   - Open `https://huggingface.co/<repo_id>` and look for the yellow
     YAML warning banner.
   - Known traps: `pipeline_tag: text2text-generation` is **invalid**
     (caught 2026-04-30) — use `text-generation` for seq2seq diacritic
     models. Per-config license overrides don't exist; repo-level only.
   - **Fix-only push:** `upload_file(path_in_repo="README.md", ...)` —
     don't re-upload weights.
3. **Every model card carries a "How we compare" matrix:** this model
   vs our other variants vs public SOTA vs other public candidates at
   similar scale vs a baseline (rule-based / cloud LLM). Bold best per
   column. Unmeasured cells = "—". Highlight the publishing model with
   `**this** →`. Add new candidates to `publish_hf.py`'s
   `COMPARISON_MATRIX`.

## Docs sync — same commit as the result

Never accumulate "docs to refresh" backlog. **Never claim a number in a
doc before it's measured.** Order: (a) measure, (b) update doc with
cited number.

| Trigger | Update in same commit |
|---|---|
| New bench number | `docs/benchmark.md` row + register-conditional production guidance |
| New HF model | `docs/recipes.md`, `docs/sota_vn_2026q2.md` or `docs/tasks/<task>.md`, `README.md` AND `README.vi.md` |
| New `nom.*` module | `docs/recipes.md`, `docs/architecture.md`, both READMEs if user-facing |
| New gotcha | This file's "VN gotchas" + relevant module docstring |
| New training run | `training/<task>/README.md` history table, `CHANGELOG.md` if version-bumped |
| Version bump | `pyproject.toml`, `CHANGELOG.md`, both READMEs |

**`README.vi.md` is a first-class peer of `README.md`** — same commit,
same structure, same status badges, same recommended-stack rows.

## Language by surface

| Surface | Language |
|---|---|
| Website (`docs/**` rendered to `nom-vn.nrl.ai`) | **Vietnamese** |
| `README.vi.md` | Vietnamese |
| HF cards (`nrl-ai/*`) | **English** (global ML community) |
| `README.md`, `CHANGELOG.md`, commit msgs, PR titles/desc | English |
| `src/` comments + docstrings, `training/` | English |
| Issue / PR comments | Mirror the questioner |
| `docs/research/` | Either; default English for academic prose |

Hard rule: **website pages = Vietnamese**. **HF cards = English.**
Quoted VN example sentences in HF cards are welcome.

### Don't mix English into VN prose unless established

Allowed verbatim in VN: `API`, `URL`, `JSON`, `HTTP`, `model`, `server`,
`client`, `file`, `LLM`, `RAG`, `OCR`, `GGUF`, `GitHub`, `HuggingFace`,
`Ollama`, `llama.cpp`, `localStorage`, `token`, `backend`, `embedding`,
`tokenizer`, `dataset`, `chunk`, plus identifiers (model IDs, env-var
names, paths, code symbols).

Translate when there's a clean VN equivalent: preset → kiểu cấu hình,
input → đầu vào, output → đầu ra, sentence → câu, word → từ, settings
→ cài đặt, reset → đặt lại, save → lưu, copy → sao chép, options →
tuỳ chọn, available → có sẵn, required → bắt buộc, "Server status" →
"trạng thái máy chủ".

Sentences must scan as VN, not bilingual code-switching. Exception:
code-voice identifiers (`NOM_LLM_BACKEND`, `top_k`) stay verbatim.

## Fast / small / nano tiers train on the SAME corpus as base

Smaller variant ≠ smaller corpus. Chinchilla-style, small models on
rich corpora generalize better. Concrete rule: every `-small` /
`-nano` run uses ≥ the `-base` corpus and epoch count. Compute saving
comes from arch + step time, not corpus thinning.

**Small-tier base for VN diacritic (2026-04-30):** `VietAI/vit5-small`
does NOT exist. Use `vinai/bartpho-syllable-base` (115M, MIT, .bin).
Syllable-level tokenizer matches per-syllable tone disambiguation.
Document SHA256-pin choice in the wrapper docstring (.bin not
safetensors; VinAI well-known but not Google/Meta-audit scale).

## Don't leak internal terms to user-facing artifacts

User-facing = HF cards, both READMEs, all `docs/`, blog posts, talks,
papers, training-script docstrings/comments, CHANGELOG.

**(a) References to this file are forbidden.** Phrases like "per
CLAUDE.md §11" leak the instruction layer. Restate self-contained:
- "per our verified-benchmarks rule" instead of "per CLAUDE.md §12"
- "our no-pickle policy" instead of "principle 11"
- "we cite Viet-Anh + Neural Research Lab on every artifact" instead
  of "principle 13"

**(b) Internal hostnames** (`genpc2`, etc.). Generic phrasing in prose
("the remote GPU host"); in scripts, parametrize through env var
(`TRAIN_HOST="${TRAIN_HOST:-genpc2}"`).

**Audit grep on every user-facing change:**

```bash
grep -rn "CLAUDE\.md\|genpc2" docs/ README.md README.vi.md \
    training/*/README.md training/*/*.py training/*/*.sh CHANGELOG.md
```

After HF push, also grep `model_info(...)` / `dataset_info(...)` text.

## Environment setup

```bash
# 1. Python 3.10+
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,chat,otel]"

# 2. Frontend (Node 20+ / pnpm 10+)
cd ui && pnpm install && cd ..

# 3. OCR (optional)
sudo apt install tesseract-ocr tesseract-ocr-vie    # or conda / brew

# 4. Hooks
pre-commit install

# 5. Local LLM
ollama pull qwen3:8b
```

Verify:
```bash
pytest                                # 250+ tests pass
cd ui && pnpm typecheck && pnpm lint && pnpm build && cd ..
nom serve --in-memory                 # then localhost:8080
```

## Code style — Python

- **Type-everywhere.** `from __future__ import annotations`. No `Any`
  in public APIs except duck-types (commented why).
- **Protocols, not ABCs.** `typing.Protocol` (`runtime_checkable` when
  `isinstance` helps). See `nom.chat.Store`,
  `nom.chat.EmbeddingsCache`. ABCs banned.
- **Frozen dataclasses for value objects.** `@dataclass(frozen=True,
  slots=True)` for hot-path immutables.
- **No mutable default args.** `field(default_factory=list)`.
- **Local imports for heavy / optional deps** (numpy, torch,
  sentence-transformers, pdfplumber). See `MemoryStore.ask`.
- **`ruff check .` + `ruff format --check .` + `mypy --strict src/`**
  must pass. Line length 100. isort-sorted imports.
- **Comments default to none.** Add only when WHY is non-obvious.
- **No `…Manager` class names** (pre-commit hook bans them).

## Code style — TypeScript / React (`ui/`)

- **Strict TS.** `strict`, `noUnusedLocals`, `noUnusedParameters`,
  `noFallthroughCasesInSwitch`. `any` warns; use `unknown` + narrow.
- **Prettier** owns formatting. 100-col, double quotes, semicolons,
  trailing commas.
- **ESLint flat config** + typescript-eslint strict + react-hooks. No
  `console` outside `warn` / `error`.
- **Functional components only.** State via `useState` / `useReducer`;
  data via TanStack Query.
- **No new global state libs** (Zustand / Redux / Jotai off the table).
- **Tailwind** with tokens in `ui/tailwind.config.ts`: cream
  `#faf6ec`, ink `#141414`, accent `#b5563a` (terracotta). Structural
  surfaces (cards, dialogs, tables, code blocks) stay sharp; only
  interactive controls (button, input, textarea) round 6px via
  `rounded-md`. Tokens stay in lockstep with the website palette in
  `docs/.vitepress/theme/custom.css` so screenshots and live UI read
  as the same product.
- **Radix primitives** copied into `ui/src/components/ui/` (ShadCN
  pattern); don't depend on `@shadcn/ui` runtime.
- **Bundle ~125 KB gzip.** Keep <200 KB unless the feature earns the
  increase.

## Test rules

- `pytest tests/` from repo root. Excluding
  `test_pipeline.py::TestOCRStage` is OK without tesseract.
- Integration tests **skip cleanly** when optional deps missing
  (`pytest.importorskip` / `skipif`).
- **No real LLM/embedder calls in unit tests.** Use `_FakeLLM` /
  `_FakeEmbedder` (see `tests/test_chat.py`).
  `tests/test_data_pipelines.py` is the integration tier.
- **Multi-store coverage:** `Store` Protocol tests use
  `@pytest.fixture(params=["memory", "sqlite"])` (see
  `tests/test_multi_space.py`).

## Pre-commit

```bash
pre-commit run --all-files
```

Runs ruff + mypy strict + codespell + markdownlint + ban-Manager-names,
plus ui-* (prettier, eslint, tsc no-emit). Never `--no-verify`.

## Run / dev commands

| Goal | Command |
|---|---|
| Chat web app, persistent (`~/.nom`) | `nom serve` |
| Same, ephemeral | `nom serve --in-memory` |
| Custom port + model | `nom serve --port 9000 --model phi4` |
| Frontend hot reload | `cd ui && pnpm dev` (proxies `/api` → :8090) |
| Build UI bundle | `scripts/build_ui.sh` |
| Tests | `pytest` |
| RAG retrieval bench | `python benchmarks/rag/bench_rag_vn.py` |
| Office fixtures | `python benchmarks/data/office_vi/_generate.py` |
| Seed demo spaces | `python scripts/seed_demo.py` |

## Screenshots — capture at desktop width

UI screenshots that land in `docs/` must be captured at a desktop
viewport (≥ 1440 × 900). The chat app's editorial 2-column layout
collapses to a single stack below ~1024 px, which makes the result
hidden behind the form on the Compliance / Admin pages and looks
cramped on the Translate / Models pages. Marketing-grade shots
require the side-by-side layout.

Concrete rules when scripting Playwright (manual or via the
`mcp__playwright__browser_resize` tool):

- Default viewport: **1440 × 900** for app pages.
- Use **1920 × 1080** when capturing pages with three or more
  columns (admin + audit, model catalog) so nothing is cropped.
- VitePress doc pages are reader-grade — capture at 1440 × 900 and
  let the `.vp-doc` 728 px max-width center naturally.
- After resizing, scroll to top before `screenshot()` so the
  header is visible.
- Save under `docs/screenshots/` with a 2-digit numeric prefix and
  copy to `docs/public/screenshots/` so VitePress serves them.

## Other reading

- [`docs/architecture.md`](docs/architecture.md) — module map
- [`docs/pipeline.md`](docs/pipeline.md) — v0.1 doc-extraction pipeline
- [`docs/benchmark.md`](docs/benchmark.md) — measured numbers
- [`docs/sota_vn_2026q2.md`](docs/sota_vn_2026q2.md) — current LLM/embed/OCR picks
- [`docs/oss_landscape_2026q2.md`](docs/oss_landscape_2026q2.md) — borrow / avoid
- [`docs/research/`](docs/research/) — deeper notes
- [`benchmarks/README.md`](benchmarks/README.md) — reproduce numbers
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — dev setup + PR rules
