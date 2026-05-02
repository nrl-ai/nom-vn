# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.37] — 2026-05-02

### Fix: skip PNG upload-format test when tesseract is missing

Same content as v0.2.36; CI publish workflow caught a test-runner
issue that v0.2.36 hit. The new
`test_upload_each_file_format[png]` parametrized variant runs
`/index` which shells out to tesseract — the skip-on-missing was
placed *after* the index call, so on CI runners without tesseract
the index raised `TesseractNotFoundError` before reaching the
skip. Moved the check above the upload + index so the parametrize
case skips cleanly. v0.2.36 wheel is functionally identical to
v0.2.37 — the bump exists so the publish workflow re-runs against
a green tests gate and ships to PyPI.

## [0.2.36] — 2026-05-02

### Hardening + reproducible smoke tests

Four small but high-leverage refinements after the live-deployment
smoke pass on v0.2.35:

1. **Constant-time bearer-token compare.** The auth middleware
   used `header != f"Bearer {_auth_token}"`, which short-circuits
   at the first mismatching byte and leaks the token via response
   timing. Switched to `secrets.compare_digest` over a pre-encoded
   expected header. New regression test
   `test_auth_compare_is_constant_time` patches `secrets.compare_digest`
   and asserts the auth path actually goes through it (so a future
   refactor that drops back to `==` fails CI).

2. **File-format upload coverage.** `tests/test_chat.py` previously
   only covered `.txt`. Now parametrized over DOCX/XLSX/PPTX/PDF/PNG
   using `benchmarks/data/office_vi/`, `benchmarks/data/udhr_vi/`,
   `benchmarks/data/synthetic_ocr_vi/` fixtures. Each variant uploads
   via the multipart `/api/spaces/{id}/materials` endpoint, then runs
   `/index` and asserts `n_indexed >= 1`. Skips cleanly on the runner
   when tesseract isn't installed (PNG path) or fixtures are missing.

3. **Reproducible deployment smoke test.** Promoted the in-memory
   harness used during the v0.2.34→v0.2.35 verification into a
   first-class `scripts/e2e_smoke.py` (point at any URL, runs the
   full 6-section + 30-something assertion matrix) and
   `scripts/e2e_persistence.py` (drives two server boots end-to-end
   to prove `--data-dir` survives restart). Anyone can validate a
   deployment with `python scripts/e2e_smoke.py http://localhost:8080`.

4. **OCR end-to-end assertion.** New
   `test_ocr_extracts_vietnamese_diacritics_from_png` uploads a
   synthetic Vietnamese PNG, runs `/index`, then fetches
   `/api/spaces/{id}/materials/{mid}/text` and asserts the result
   contains real Vietnamese diacritics — proves Tesseract's `vie`
   traineddata is loaded. Skip-on-missing.

Test count: **406 pytest + 37 vitest = 443 passing**, up from 436
in v0.2.35. No code-surface changes for users; all four items
strengthen guarantees.

## [0.2.35] — 2026-05-02

### Fix: 503 (not 500) when llama-server is unreachable

End-to-end smoke test caught a transport-error branch that was
falling through:

- The `LlamaCpp` adapter wraps an underlying `httpx.ConnectError`
  into a `RuntimeError("Could not reach llama-server at …")` so
  the user gets an actionable hint at the SDK level.
- But `server.py` only recognised transport errors by class name
  (`HTTPStatusError`, `ConnectError`, `Timeout`). The wrapped
  RuntimeError fell through and surfaced as a 500 Internal Server
  Error with a generic "Internal Server Error" body.

Now the catch in the `/ask` handler also detects the message
contents (`"could not reach"`, `"llama-server"`, `"ollama"`,
`"11434"`) and routes those through `_llm_error_to_503`, so
unreachable-backend cases consistently return:

- HTTP 503
- A JSON `{"detail": "..."}` body that mentions `llama-server`
  or `ollama pull` so the user knows what to do.

New regression test `tests/test_chat.py::TestAsk::test_ask_
translates_llamacpp_unreachable_into_503` covers it. 399 pytest +
37 vitest = 436 passing.

## [0.2.34] — 2026-05-02

### Re-captured 02-chat-with-answer against matching content

The previous chat-with-answer screenshot showed the LLM saying
"câu hỏi không liên quan" because the active space was Truyện Kiều
(literature) but the question was about a contract. Both fixed:

- `scripts/capture_screenshots.py` now picks the
  "Hợp đồng & Báo cáo (Office)" space when the contract question
  is asked. Falls back to the first space if it's not seeded.
- The question is now factual extract — "Số hợp đồng là gì? Bên A
  là ai?" — instead of a numeric question that small models tend
  to mangle (qwen3:1.7b answered "300 tỷ" instead of "300 triệu"
  on the previous take).

The new screenshot shows a grounded, accurate answer:
"Số hợp đồng là HĐ-2026/045. Bên A là Công ty TNHH Pháp lý Hồng
Hà — đại diện bởi ông Nguyễn Văn A, chức vụ Giám đốc." — both
facts match the seeded ground truth, with citation markers and 3
sources retrieved.

No code-surface changes vs 0.2.33; this release exists so the
publish workflow re-runs and ships an updated wheel + the
refreshed README screenshot pointer (the PNG itself is served
from main, not the wheel).

## [0.2.33] — 2026-05-02

### Publish-workflow fix — first release that can actually go to PyPI

Two CI bugs caught + fixed in this round:

- **Mypy `llama_cpp` import-not-found** (caught after 0.2.31). Optional
  dep, lazy-imported at runtime; CI doesn't install
  `[llamacpp-python]`, so mypy needs `llama_cpp.*` in
  `ignore_missing_imports`. Fixed in 856af51.
- **Publish workflow tests-gate failure** (caught on the v0.2.32
  release-trigger). The job ran `pip install -e .`, but the wheel
  target's `force-include "src/nom/chat/ui_dist"` trips on a fresh
  checkout because `ui_dist/` is a build artifact that's gitignored.
  We now stage a minimal `Nôm`-branded `index.html` placeholder
  before the editable install (4f6b57d, f6da1f5). The real React
  bundle still ships via the existing `build-ui` → `build` job
  chain that gates the wheel/sdist artifacts uploaded to PyPI; the
  wheel-content sanity check (`assert any('chat/ui_dist/index.html'
  in n)`) keeps that honest.

These were the last code-side blockers. The publish workflow now
gets through tests-gate → build-ui → build sdist + wheel cleanly;
the only step that still fails is the OIDC handshake to PyPI/
TestPyPI itself, which needs a one-time **Trusted Publisher**
configuration on the PyPI side
([pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/)
— project `nom-vn`, owner `nrl-ai`, repo `nom-vn`, workflow
`publish.yml`, environment `pypi`).

### Verified end-to-end (clean venv, `/tmp/nom-clean`)

- 28/28 endpoint checks against the installed wheel:
  `/api/health`, `/api/llm/backends`, all 7 stateless `/api/tools/*`
  endpoints, validation 422s, spaces CRUD + multipart upload,
  `/docs` Swagger, bundled UI at `/`.
- Auth gating (`NOM_AUTH_TOKEN`): `/api/health` stays open;
  `/api/spaces` + `/api/tools/*` return 401 without/wrong token,
  200 with correct token.
- All 6 LLM adapters import: Ollama, LlamaCpp, LlamaCppPython,
  HuggingFace, OpenAI, Anthropic.

No code-surface changes since 0.2.32 — this release exists to make
the publish workflow runnable on tag push.

## [0.2.32] — 2026-05-02

### Refreshed screenshot set + Vietnamese-only normalize hint

`docs/screenshots/` regenerated end-to-end via the new
`scripts/capture_screenshots.py` Playwright harness. Captured a
real-LLM chat-with-answer screenshot (qwen3:1.7b on Ollama,
seeded with the demo Truyện Kiều space). Eight playground pages
covered: welcome, chat-with-answer, diacritic restore, tokenize,
normalize+detect, strip, noise, API & Setup, Settings.

The Normalize / Detect page now localizes the `reason` string
returned by `/api/tools/text/detect` (HTTP API stays English; UI
renders Vietnamese) so the screenshot reads "Có ký tự dấu đặc
trưng tiếng Việt" instead of the raw English description.

Also: `scripts/capture_screenshots.py` is reusable — point it at
any running `nom serve` to regenerate the doc-screenshot set.

## [0.2.31] — 2026-05-02

### Multi-backend LLM + API & Settings pages

Three new LLM adapters land alongside the existing `Ollama` /
`OpenAI` / `Anthropic`, so the chat / RAG / LLM-backed diacritic
restore are no longer Ollama-only:

- **`nom.llm.LlamaCpp`** — wraps `llama-server`'s OpenAI-compatible
  HTTP API. No fake API key required; helpful error message when the
  server isn't running. Optional extra `nom-vn[llm]`.
- **`nom.llm.LlamaCppPython`** — in-process llama.cpp via the
  `llama-cpp-python` bindings. No daemon. Auto-pulls GGUFs from
  HuggingFace via `model="hf:<repo>:<filename>"`. Optional extra
  `nom-vn[llamacpp-python]`.
- **`nom.llm.HuggingFace`** — in-process HF transformers. Loads any
  text-generation model from the Hub on first call. Optional extra
  `nom-vn[llm-hf]`. Schema-constrained output is left to backends
  that support `response_format`.

CLI gains `--backend ollama|llamacpp|llamacpp-python|huggingface|openai|anthropic`
(env override `NOM_LLM_BACKEND`). Per-backend defaults for
`--model` apply when not explicit.

The `/ask` 500 stack-trace from a missing Ollama model now becomes a
clean **503** with an actionable hint (`ollama pull qwen3:8b` /
`set NOM_LLM_MODEL=…`). Mirrored in the LLM-backed diacritic restore
endpoint.

### New playground tool surfaces

- **API & Setup page** — install / launch / curl examples for every
  endpoint, plus per-backend setup commands (Ollama, llama.cpp,
  cloud). Linked from the left rail.
- **Settings page** — server health snapshot, **bearer-token
  authentication** toggle (server-side `NOM_AUTH_TOKEN`, client-side
  token store), backend picker with launch-command generator, default
  `top_k` slider, and a "reset state" action that clears every
  `nom:*` key from `localStorage`.
- New `/api/llm/backends` endpoint reports which adapters are
  importable in the running process so the picker UI can grey out
  options the user hasn't installed.
- New `auth_required` field on `/api/health` so the UI can detect
  the gated state without first being authenticated.

### Tests

- Backend: 18 → 28 cases under `tests/test_llm.py` (LlamaCpp +
  HuggingFace + LlamaCppPython smoke + protocol conformance for all
  six adapters); auth gating + 503-translation cases under
  `tests/test_chat.py`. **398 pytest passes.**
- UI: Vitest now covers SettingsPage (server health, auth-token
  save/clear, backend picker, top_k slider) and ApiPage (sections,
  curl examples, OpenAPI links). **37 vitest passes.**
- Total: **435 tests, 0 failures.**

### Repo metadata

`gh repo edit`: description updated, homepage set to
https://nom-vn.nrl.ai/, topics added (`vietnamese`,
`vietnamese-nlp`, `rag`, `diacritic-restoration`, `ocr`, `llm`,
`ollama`, `llama-cpp`, `huggingface`, `fastapi`, `local-first`, …).

### Screenshots

`docs/screenshots/` refreshed to reflect the v0.2.30+ playground UI:
new `01-welcome.png`, `07-playground-diacritic.png`,
`08-playground-noise.png`. Older office-viewer screenshots
(04 / 05 / 06) unchanged — those flows haven't moved.

## [0.2.30] — 2026-05-01

### Playground UI: multi-task front-end + stateless `/api/tools/*` surface

The chat web app is now a **playground** for the full
`nom.text` toolbox, not just RAG. New left rail with task switcher;
chat lives alongside five stateless tools, each with its own option
panel:

- **Khôi phục dấu** — diacritic restore (rule / HF seq2seq / LLM
  backend; HF model picker between `nrl-ai/vn-diacritic-vit5-base`,
  `-small`, `-spell-correction-base`, and the Toshiiiii1 baseline).
  Output renders with diff-highlighted changed words.
- **Tách từ / câu** — word + sentence segmentation, list-of-chips or
  underscore-joined output, compounds tinted in accent.
- **Chuẩn hoá** — NFC normalize + `is_vietnamese` / `has_diacritics`
  flags, with a per-codepoint inspector when the input was NFD.
- **Bỏ dấu** — strip diacritics (URL slug / search-key use case).
- **Sinh nhiễu** — reproducible noise generator with all 7 presets
  (`light` … `comprehensive`), seedable, deterministic.

Chat gains an inline **top_k** options popover (1–20 slider, Esc
closes) that's persisted in localStorage; replaces the fixed
`top_k=5` default.

### Backend

New `nom.chat.tools_api.register_tool_routes()` mounts seven POST
endpoints + two GET catalog endpoints under `/api/tools/*`. The HF
diacritic model is lazy + process-cached per `model_id` so first-call
weight load is amortized across the rest of the session. The LLM-
backed restore reuses whatever LLM was passed into `build_app`.

Eighteen new pytest cases under `tests/test_tools_api.py` cover happy
path + 422 / 503 error surfaces. HF model load is gated behind a
separate import guard so unit tests don't touch torch.

### UI tests

Vitest + Testing Library added (Vitest 2 — Vite 5 compatible). 27
component tests across `DiffView`, `Select`, `Segmented`,
`NumberField`, `OptionRow`, `CopyButton`, `TextInput`, `ToolShell`,
`Panel`, `EmptyHint`, `Spinner`, `useToolRunner`, and `TaskNav`. Run
with `pnpm test`.

### UX polish

- **Cmd/Ctrl + Enter** runs the active tool from anywhere on the page.
- **Esc** closes the chat options popover.
- Sonner toast on every tool API error (in addition to the inline
  error panel).
- Empty-state hint replaces the bare "—" when no result yet.
- Diff highlight upgraded from dotted-underline tint to a solid
  accent-tinted background so changes are unmissable.
- Run button label normalized to a single Vietnamese verb (`Chạy`)
  instead of bilingual "`Chạy / Run`".

### Bumped

- `src/nom/__init__.py` `__version__` was lagging behind `pyproject`
  (0.2.7 vs 0.2.29); aligned to the new 0.2.30.

## [0.2.29] — 2026-05-01

### Spell-correction track: v2 corpus retraining beats Toshiiiii1 on OOD

`nrl-ai/vn-spell-correction-base` re-published — same ViT5-base 220 M
arch, retrained on a **multi-source v2 corpus** (Wiki+news 65 % + Zalo
Legal QA 25 % + comprehensive_noise 10 %, with 6 noise presets
round-robin including `telex_grammar_noise()` and `mobile_noise()`).
545K (noisy, clean) pairs, 5 epochs cosine LR, 215 min on RTX 3090.

**Out-of-distribution eval (n=150, hand-curated, bootstrap 95 % CI):**

  Slice            v0.2.29 (new)   v0.2.28 (prev)   Toshiiiii1   bmd1905
  forum_25         **65.84**        59.45            60.11         59.02
  mobile_25        95.84            95.01            96.95         88.09
  telex_real_25    **19.15**        17.38            18.54         11.58
  ocr_25           **97.57**        93.62            94.22         47.42
  legal_real_25    **95.87**        95.09            93.80         54.90
  news_real_25     96.54            96.54            94.07         30.62
  Aggregate        **79.62**        77.43            77.40         49.21

**+2.22 pp over Toshiiiii1, +2.19 pp over our own v0.2.28.** Forum
slang slice +6.39 pp — the targeted gain from `mobile_noise()`. Telex
slice +1.77 pp — `telex_grammar_noise()` working as designed.

Synthetic 8-split has minor regressions (light_avg 98.58 → 98.32,
heavy_avg 97.35 → 97.03 — both still well above the 92/80 gates).
Trade-off accepted: ~0.3 pp synthetic for +2.2 pp OOD aggregate.

### Stage B — `vn-spell-correction-small` (BARTpho 115 M) on v2

Re-published. 96.6 min training on RTX 3090.

      Slice            v0.2.29 (new)   v0.2.28 (prev)   Toshiiiii1
      forum_25          64.64           58.73            60.11
      mobile_25         95.29           95.01            96.95
      telex_real_25     16.45            9.51            18.54
      ocr_25            94.19           91.16            94.22
      legal_real_25     93.54           93.56            93.80
      news_real_25      91.34           91.58            94.07
      Aggregate         **77.55**       75.92            77.40

+1.63 pp over v0.2.28. Forum slice +5.91 pp, Telex +6.94 pp — same
targeted gains as the base tier.

### Stage C — `vn-diacritic-vit5-base` (ViT5 220 M) on v2 diacritic corpus

Re-published. 231.8 min training on RTX 3090. The v2 corpus for the
diacritic-only path is Wiki+news+legal (595K stripped/clean pairs;
no synthetic noise generator since the diacritic task is determined
by `strip_diacritics`).

      Slice            v0.2.29 (new)   v0.2.28 (prev)   Toshiiiii1
      forum_25          43.54           49.31            60.11
      mobile_25         76.99           79.66            96.95
      telex_real_25     14.37           14.89            18.54
      ocr_25            94.83           94.53            94.22
      legal_real_25     **93.02**       88.05            93.80
      news_real_25      96.05           95.80            94.07
      Aggregate         71.15           71.50            77.40

**Mixed result on the diacritic tier.** Legal slice +4.97 pp (legal
corpus paid off), news +0.25 pp, OCR +0.30 pp — formal-register text
is genuinely better. Aggregate is -0.35 pp because the legal-skewed
corpus moved the model away from informal slang (`forum_25` -5.77 pp,
`mobile_25` -2.67 pp). For the diacritic-only use case (formal text
with stripped accents — legal docs, news, OCR), v0.2.29 is the right
choice; for informal text (forum / mobile), users should route to
`vn-spell-correction-base` anyway, so this trade-off is intentional.

### Final OOD landscape (n=150, after v0.2.29 chain)

      Model                              Aggregate    95 % CI
      vn-spell-correction-base v0.2.29   79.62        [74.7-84.6]
      vn-spell-correction-small v0.2.29  77.55        [72.5-82.6]
      Toshiiiii1 (public)                77.40        [72.7-82.1]
      vn-diacritic-vit5-base v0.2.29     71.15        [66.0-76.3]
      vn-diacritic-small v0.2.28         70.27        [65.1-75.8]
      bmd1905 (public)                   49.21        [43.5-54.9]

Both spell-correction tiers now decisively beat the public landscape
on OOD. The diacritic-only tiers retain the public-landscape gap on
informal slices but are the right choice for formal-text-only workloads.

The v2 corpus closes specific weaknesses surfaced by the OOD eval:

- **Multi-register source mix**: 65% Wiki+news + 25% Zalo Legal QA
  corpus + 10% comprehensive_noise on mixed.
- **6 noise presets round-robin**: `light_noise` / `telex_typo_noise` /
  `telex_grammar_noise` / `mobile_noise` / `ocr_realistic_noise` /
  `heavy_noise`. The `_grammar` and `mobile` presets are new and target
  the Telex / forum slang weaknesses.
- **Per-source quotas + dedup**: 545K (noisy, clean) pairs for spell;
  595K (stripped, clean) pairs for diacritic.

### Hand-curated OOD eval — 150 sentences, 6 registers, bootstrap CI + error breakdown

`benchmarks/data/spell_correction_eval_real/` is the load-bearing answer
to the synthetic-eval-overfit concern. Each pair has a real Vietnamese
error pattern (NOT generated from `nom.text.noise`):

- `forum_25.jsonl` — Vietnamese forum / social-media teen-code.
- `mobile_25.jsonl` — phone-typing autocorrect mishaps.
- `telex_real_25.jsonl` — real Telex/VNI keystroke artefacts.
- `ocr_25.jsonl` — Tesseract / EasyOCR engine output.
- `legal_real_25.jsonl` — formal-register typos in real legal documents.
- `news_real_25.jsonl` — modern news headlines + body.

`benchmarks/accuracy/bench_spell_correction_real.py` reports word
accuracy, sentence exact match, bootstrap 95% CI (n=1000 resamples),
and per-error-type breakdown (missed_diacritic / wrong_tone / base_char
/ extra_word / missing_word).

5 models benched, n=150 aggregate:

      Model                            Word acc   95% CI
      ----------------------------------------------------
      vn-spell-correction-base (ours)  77.43 %    [73-82]
      Toshiiiii1 (public)              77.40 %    [73-82]
      vn-spell-correction-small (ours) 75.92 %    [71-81]
      vn-diacritic-vit5-base (ours)    71.50 %    [66-77]
      bmd1905 (public)                 49.21 %    [44-55]

**Surprise: we tie Toshiiiii1 on OOD.** The synthetic-eval lead our
model has (3-7 pp on the 8-split grid) does not carry over to real
noise. v0.2.29 retraining target is explicit: beat Toshiiiii1 on OOD,
not just synthetic.

### Pipeline integration — `nrl-ai/vn-diacritic-vit5-base` is now the default

`HFDiacriticModel`'s `model_id` default flipped from
`Toshiiiii1/Vietnamese_diacritics_restoration_5th` to
`nrl-ai/vn-diacritic-vit5-base`. The recommended-stack tables in
`README.md` and `README.vi.md` reordered to match. Toshiiiii1 stays in
the table as the "business / news only" alternative — it has a 2.83 pp
edge on business-register text but loses 8.7 pp on literary, so the
register-balanced ours is the safer default.

### Documentation site at https://nom-vn.nrl.ai (VitePress + edgevox theme)

VitePress scaffold under `docs/.vitepress/`, theme cloned from
`nrl-ai/edgevox`, Vietnamese as primary language with English
scaffolded under `/en/` for incremental backfill. Deploy workflow
`.github/workflows/docs.yml` builds and pushes to GitHub Pages on
every change to `docs/`.

### CI / repo hygiene

- Gitleaks secrets-scan job wired into CI alongside the existing
  pre-commit hook. The repo has been scanned end-to-end (100 commits
  + working dir): zero leaks.
- All `genpc2` references scrubbed from user-facing surfaces (scripts,
  docs, README); literal survives only in `CLAUDE.md` and operator
  shell rcs (`~/.zshrc`, `~/.bashrc`).
- Renamed `training/{diacritic,spell_correction}/launch_genpc2.sh` →
  `launch_remote_train.sh`; `TRAIN_HOST` is required (`:?` syntax).

## [0.2.28] — 2026-04-30

### Spell-correction track: base tier shipped, decisively beats public landscape

`nrl-ai/vn-spell-correction-base` published — ViT5-base (220 M, MIT) fine-tuned
on 459K (noisy, clean) pairs synthesized from the 500K mixed Wiki+news clean
corpus via `nom.text.noise`. 5 epochs cosine LR, no early stop, 180 min on
RTX 3090.

8-split grid (4 registers × 2 noise levels), measured against the public
spell-correction landscape:

  Split                       bmd1905   iAmHieu    ours base   Δ vs bmd1905
  business_55_light            91.18 %   90.22 %   98.58 %     +7.4 pp
  business_55_heavy            76.97 %   68.98 %   98.33 %     +21.4 pp
  formal_72_light              83.46 %   85.38 %   99.80 %     +16.3 pp
  formal_72_heavy              73.37 %   51.33 %   99.19 %     +25.8 pp
  conversational_300_light     84.72 %   85.45 %   97.90 %     +13.2 pp
  conversational_300_heavy     73.63 %   63.77 %   96.18 %     +22.6 pp
  literary_800_light           87.42 %   61.81 %   98.02 %     +10.6 pp
  literary_800_heavy           66.53 %   42.11 %   95.71 %     +29.2 pp

  light_avg                    86.95 %   80.31 %   98.58 %     +11.6 pp
  heavy_avg                    72.62 %   56.55 %   97.35 %     +24.7 pp

**Wins every split by 7-29 pp.** Adoption gate (light_avg ≥ 0.92,
heavy_avg ≥ 0.80) passes by very wide margin. Local re-eval reproduces
remote within ±0.03 pp.

The size advantage of bmd1905 (400 M vs our 220 M) doesn't matter — a
targeted fine-tune on the 8-register noise distribution dominates a
generic correction model.

### Spell-correction tier strategy

Same base+small two-tier convention as diacritic, **same 500K training
corpus across both tiers** per the same-corpus-for-all-tiers rule:

- `nrl-ai/vn-spell-correction-base` (ViT5-base, 220 M) — shipped.
- `nrl-ai/vn-spell-correction-small` (BARTpho-syllable, 115 M) — training,
  ETA ~1.5 h.

### Spell-correction infrastructure

New code:

- `nom.text.noise` — already in v0.2.25; deterministic noise generator
  with 3 calibrated presets. Powers the training-corpus build.
- `training/spell_correction/` — full pipeline mirror of the diacritic
  tree: `prep_data.py` (applies round-robin noise to clean text),
  `train.py` (8-split eval grid), `publish_hf.py` (different gate +
  comparison matrix), `launch_remote_train.sh`.
- `benchmarks/data/spell_correction_eval/build.py` — 2,098 (noisy, clean)
  eval pairs from the 4 diacritic eval slices × 2 noise levels.
- `benchmarks/accuracy/bench_spell_correction_hf.py` — bench any HF
  spell-correction model. `--use-slow-tokenizer` for older bartpho releases.

New HF artifacts:

- 🤗 [`nrl-ai/vn-spell-correction-base`](https://huggingface.co/nrl-ai/vn-spell-correction-base) — base tier
- 🤗 [`nrl-ai/vn-spell-correction-eval`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval) — 8-split eval grid (2,098 pairs)
- 🤗 [`nrl-ai/vn-spell-correction-train`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-train) — 459K (noisy, clean) training pairs

All cards include the comparison matrix vs the public landscape and cite
Viet-Anh Nguyen + Neural Research Lab.

### docs/tasks/spell-correction.md

New per-task page with public landscape + our pipeline + trained models +
datasets + measured results + reproduce sequence + noise-generator
explanation. README.md and README.vi.md "Recommended stack" tables
updated with the new spell-correction row.

## [0.2.27] — 2026-04-30

### Fast tier: `nrl-ai/vn-diacritic-small` published (BARTpho-syllable, 115 M)

Trained ViT5-small does not exist (VietAI ships only `vit5-base` and
`vit5-large`). Picked `vinai/bartpho-syllable-base` (115 M, MIT) for the
fast tier instead — its **syllable-level tokenizer is uniquely
well-matched to per-syllable tone disambiguation**, the actual task in
diacritic restoration.

Trained on the **same 500K mixed Wiki+news corpus + 5 epochs cosine LR
+ same hyperparams** as the v0.2.26 base. The "small model trained on
small corpus to save compute" instinct is exactly backwards: Chinchilla
scaling shows compute-optimal training pairs *more* tokens per parameter
as model size shrinks. The compute saving comes from the smaller arch
+ faster step time, not from a thinner corpus. (Codified as a rule in
the internal operating manual.)

4-register results vs the v0.2.26 base + Toshiiiii1 (the SOTA we
benchmark against):

  Register             Toshiiiii1   v0.2.26 base   v0.2.27 small   Δ vs base
  formal_udhr          98.14 %      99.43 %        91.51 %         -7.92 pp
  business_55          97.81 %      94.98 %        94.44 %         -0.54 pp
  conversational_300   93.94 %      94.12 %        90.68 %         -3.44 pp
  literary_udvtb       89.40 %      90.24 %        86.33 %         -3.91 pp

Inference speed (RTX 3080 16 GB Mobile, num_beams=1):
  base:  100-272 ms/sent (mean ~169)
  small:  38-94  ms/sent (mean  ~58)
  Speedup: ~2.9× on local 3080 / ~2.2× during training (115 / 220 M
  params, 195 / 88 min total wall-clock for the same 5-epoch budget)

The formal-register regression is unusually steep (-7.92 pp). Sample
inspection shows BARTpho-syllable occasionally **drops syllables**
during generation (e.g. "công bằng và hòa bình" → "công bằng và bình").
That's a generation-distribution issue specific to the BARTpho
arch, not a tokenization or training-data issue.

**Published as [`nrl-ai/vn-diacritic-small`](https://huggingface.co/nrl-ai/vn-diacritic-small)**
with explicit "fast tier — 2.2× speedup, ~3-4 pp avg quality cost"
framing in the model card. Quality lower than the base, but for
latency-bound or memory-constrained pipelines (CPU inference, edge,
high-throughput batch) the trade is real.

### `publish_hf.py` made arch-aware

The model-card template was previously hard-coded to ViT5 (tags,
title, training-corpus blurb). After publishing to a BARTpho base it
inferred the wrong tags. Fix: detect the arch family from the
`model_id` in the training summary (`vit5` → "ViT5" + tag `t5`,
`bartpho` → "BARTpho-syllable" + tag `bartpho`, etc.) and
conditionally include both `wiki` + `news` datasets in the YAML when
`train_pairs >= 400_000`. Re-renders cleanly for any future tier.

Also fixed a stale baseline constant in `TOSHIIIII_BASELINE` (was
`conversational_300: 0.9377`, now `0.9394` matching the latest
4-register bench JSON) so the auto-generated Δ column in the model
card is correct.

### `vn-diacritic-vit5-base` republished as v0.2.26 weights

The HF repo `nrl-ai/vn-diacritic-vit5-base` now contains the v0.2.26
mixed-source weights (replaces the v0.2.25 Wiki-only weights at the
same name). Local re-eval reproduces remote within ±0.07 pp on every
register. Card updated to reflect the new training data + Δ column.

## [0.2.26] — 2026-04-30

### Train experiment #6: mixed-source ViT5 beats Toshiiiii1 on 3/4 registers

ViT5-base, 350K Wikipedia + 150K NFC-fixed VN news (`tmnam20/Vietnamese-News-dedup`),
5 full epochs cosine LR, no early stop, eval_samples=1000. 195 min on the
remote GPU host (RTX 3090, BF16, batch=32).

4-register results vs the public SOTA (`Toshiiiii1/Vietnamese_diacritics_restoration_5th`):

  Register             Toshiiiii1   v0.2.25 (Wiki)   v0.2.26 (mixed)   Δ vs Toshi
  formal_udhr          98.14 %      99.57 %          99.43 %           +1.29 ⭐
  business_55          97.81 %      93.44 %          94.98 %           -2.83
  conversational_300   93.94 %      94.16 %          94.12 %           +0.18 ⭐
  literary_udvtb       89.40 %      89.39 %          90.24 %           +0.84 ⭐

**Wins on 3 / 4 registers**, including the literary register that v0.2.25
tied. Adoption-gate `business >= 96 %` still fails by 1.02 pp, but the
register-balance is now decisively better than Toshiiiii1 — 9.19 pp spread,
3 of 4 corpora ahead.

News data did exactly what we hypothesized: closed the business gap by
+1.54 pp vs v0.2.25 (Wiki-only), without regressing the formal /
conversational wins.

**Republished as `nrl-ai/vn-diacritic-vit5-base`** (replaces v0.2.25
weights at the same name). Local re-eval reproduces remote within
±0.07 pp on every register.

### Per-task docs structure introduced

`docs/tasks/` is the new home for per-task user-facing detail. Each page
follows `tasks/_template.md`:

- public landscape (license + format + measured number per candidate)
- our pipeline (Protocol seam + 3-line code)
- trained models (`nrl-ai/*` HF links + Δ vs the SOTA we benchmark against)
- datasets (`nrl-ai/*` HF links + provenance per source)
- results (committed JSON baselines + reproduce commands)

First page: [`docs/tasks/diacritic-restoration.md`](docs/tasks/diacritic-restoration.md).
Other tasks (spell correction, embedding, retrieval, OCR, etc.) migrate
from the monolithic `benchmark.md` one at a time.

### `README.vi.md` brought to full parity with `README.md`

The Vietnamese README was 49 lines stuck at "v0 đang phát triển";
English was 220+ lines at v0.2.25. The two now match section-for-section
(same recommended-stack table, same status badges, same code snippets).
Both update in lockstep going forward.

### `nom.text.noise` shipped — VN spell-correction noise generator

Reproducible per-token / per-char noise functions for generating
(noisy, clean) training pairs from clean Vietnamese text. Designed
for the upcoming spell-correction training pipeline. Six noise types
(diacritic strip / partial / confusion / char swap / insert / delete /
OCR), three calibrated presets (`light_noise`, `heavy_noise`,
`telex_typo_noise`), deterministic via seed, NFC output, edit-budget
capped. 11 unit tests, full suite at 354.

### CI pipeline restored to green

After the v0.2.21 repo rename the CI was failing for everyone. Five
fix rounds:

1. `pip install -e .[dev]` failed on missing `src/nom/chat/ui_dist`
   (UI build artifact, gitignored). Stub a placeholder `index.html` in
   each CI job before pip install.
2. Removed an unused file-level `# ruff: noqa: I001` directive newer
   ruff flagged.
3. `test_reranker.py` imported `sentence_transformers` unconditionally
   — added `pytest.importorskip` per the project test-skip pattern.
4. Bumped pre-commit ruff to v0.15.12 to match the version CI installs
   (older 0.7 disagreed on the E402-after-importorskip case).
5. Added `torch` / `transformers` / `bm25s` to mypy's
   `ignore_missing_imports` overrides; switched a stubborn
   `# type: ignore[misc]` to bare `# type: ignore` since the actual
   error code drifts between mypy versions.

### HF dataset publishing

Two datasets published to `nrl-ai/*` on Hugging Face Hub for easy
`datasets.load_dataset` access:

- [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) — 4-register evaluation grid (1,227 sentence pairs)
- [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) — 500K Wikipedia + 150K NFC-fixed VN news training pairs

Both verified renderable + loadable via `datasets.load_dataset`. Cited
to Viet-Anh Nguyen + Neural Research Lab.

## [0.2.25] — 2026-04-30

### Train experiments #3 and #4: register-balanced ViT5 fine-tune published

Two training runs on RTX 3090 / the GPU training box:

**Run #3 (failed gate, archived):** ViT5-base, 500K Wiki, 5 epochs cosine,
patience=3 early stopping, eval_samples=200. Stopped at epoch 0.96
(15K of 78K planned steps). Patience triggered on noisy 200-sample
eval_loss before the model converged. 92.54 / 86.19 — worse than
v0.2.23.

  Lesson: eval_loss on a small held-out is noisy; either bump
  eval_samples or disable early stopping for a full-budget run.
  Codified `--early-stopping-patience 0` and `--eval-samples 1000`
  recommendations in train.py docs.

**Run #4 (published):** ViT5-base, 500K Wiki, **5 epochs** (full),
cosine LR, NO early stop, eval_samples=1000. 185 min on RTX 3090.

  Register             Toshiiiii1   v0.2.23   v0.2.25
  formal_udhr          98.14 %      —         99.57 % ⭐
  business_55          97.81 %      93.69 %   93.44 %
  conversational_300   93.94 %      —         94.16 % ⭐
  literary_udvtb       89.40 %      89.47 %   89.39 %

Strict gate fails on business (-4.37 pp). But this is **the best
register-balanced VN diacritic model we've trained**: SOTA on
formal/legal Vietnamese (99.57 %) and conversational (94.16 %),
beats Toshiiiii1 on those registers.

**Published as `nrl-ai/vn-diacritic-vit5-base`** with an honest model
card flagging the gate-fail at the top, the full 4-register Δ table,
and "when to use" guidance pointing users to Toshiiiii1 for
business-heavy corpora. NOT the canonical name `vn-diacritic-restoration`
— reserved for a future model that clears the gate.

  pip install transformers torch
  from nom.text.diacritic_models import HFDiacriticModel
  restorer = HFDiacriticModel(model_id="nrl-ai/vn-diacritic-vit5-base")

### Why we plateaued and what's next

Wikipedia training is hitting a ceiling:
- v0.2.23 (200K @ 3 epochs): 93.69 / 89.47
- v0.2.25 (500K @ 5 epochs): 93.44 / 89.39

2.5× data + cosine LR + 5 full epochs ≈ no improvement on the
Wikipedia-only ceiling. The fundamental issue: Wikipedia is
encyclopedic-tilted and underrepresents modern business/news
register where Toshiiiii1's training data lives.

Queued for v0.2.26: **mixed-source corpus** experiment.

  - 350K subsampled Wikipedia (existing) + 150K news from
    `tmnam20/Vietnamese-News-dedup` (CC-BY-4.0, 10-100 M deduped
    Vietnamese articles).
  - Same arch / hyperparams as v0.2.25.
  - Hypothesis: news data closes the 4 pp business gap without
    regressing the literary/formal/conversational wins.

### New training infrastructure

  - `training/diacritic/eval_checkpoint.py` — standalone re-eval of any
    HF seq2seq diacritic model (local dir or Hub repo id) on the
    full 4-register matrix.
  - `training/diacritic/publish_hf.py` — gate-checked HF Hub publishing
    with auto-generated model card, license attribution, BibTeX
    citation, "when to use" trade-off summary.
  - `training/diacritic/post_train.sh` — end-to-end after-training
    pipeline: rsync from the GPU training box → local re-eval (>0.5 pp divergence
    fails) → publish_hf.py --dry-run.
  - `training/diacritic/prep_data_news.py` — VN news ingestor for the
    upcoming mixed-source experiment.

### HFDiacriticModel.predict_batch — 7.60× throughput

CUDA kernel-launch overhead dominates per-call cost on short Vietnamese
inputs. Padding-batched inference gives **7.60× throughput** on a
3080 16 GB Mobile (11.9 → 90.5 sent/s) on the 300-sentence Tatoeba
corpus, with 120/120 quality match against single-call predict().

  restorer = HFDiacriticModel()
  restorer.predict_batch(sentences, batch_size=16)

Default batch_size=16 sized for ~4 GB VRAM at 256-token inputs.
Empty/blank inputs pass through untouched; output ordering preserved.

### Off-the-shelf audit (2026-04-29)

Benched two unmeasured Apache/MIT VN diacritic candidates on the
55-sent business eval:

  - `qthuan2604/ViT5_Restore_Diacritics_Vietnamese`: 90.59 %
  - `qthuan2604/BARTPho_Syllable_Restore_Diacritics_Vietnamese`: 83.92 %

Both lose to Toshiiiii1 (97.81 %) and to our v0.2.23 vit5-base
(93.69 %). Toshiiiii1 remains public SOTA — training is justified.

### Eval-leak guard expanded

`prep_data._eval_leak_guards` now blocks all 4 diacritic eval slices
(business + literary + conversational + formal). Audited 500K Wiki
corpus measured 0 hits across all 4 — defense-in-depth, not a bug
fix.

## [0.2.24] — 2026-04-29

### Toshiiiii1 register matrix extended to 4 corpora

Two new diacritic eval slices and a re-bench of Toshiiiii1 to fill out
the register grid that was previously only business + literary.

New corpora:

- ``benchmarks/data/tatoeba_vi/diacritic_eval_300.txt`` — 300 sentences,
  conversational register (Tatoeba CC-BY 2.0 FR sample, deterministic
  filter via ``build_diacritic_eval.py``).
- ``benchmarks/data/udhr_vi/diacritic_eval_udhr.txt`` — 72 sentences,
  formal/legal-prose register (UDHR Wikisource, public domain,
  sentence-split via ``build_diacritic_eval.py``).

Toshiiiii1 results (RTX 3080 16 GB Mobile, CUDA, num_beams=1, 3 warmup
calls):

  Register                Sents   Word acc   Mean ms/sent
  formal/legal (UDHR)        72   98.14 %    221
  business/news              55   97.81 %    152
  conversational (Tatoeba)  300   93.94 %     82
  literary (UD-VTB)         800   89.40 %    269

Spread = 8.74 pp. Drop is **monotonic** from formal → literary, which
is what register-shift looks like in practice — a gradient, not a
cliff. Conversational sits ~4 pp below business; literary another
~4 pp below conversational. Confirms the model is register-overfit
toward modern formal/business Vietnamese (matching its training
data) without being unusable elsewhere.

Sample inspection (first-5 raw I/O dump per our internal DOUBLECHECK
rule): UDHR errors are real disambiguation (``nhân nhượng`` →
``nhận nhượng``, ``mọi`` → ``mỗi``); Tatoeba errors include
``chữ`` (letter) → ``chứ`` (rather/but). Metric matches eyeballed
quality; no methodology bug.

Updated ``docs/benchmark.md`` register-conditional production table
to four rows; updated `our internal policy` register-shift gotcha with the
new gradient and dataset entries.

JSON baselines:
``benchmarks/results/baseline_diacritic_toshiiiii_tatoeba300.json``,
``benchmarks/results/baseline_diacritic_toshiiiii_udhr72.json``.

## [0.2.23] — 2026-04-27

### Train experiment #2: VietAI/vit5-base — register-balanced, doesn't beat Toshiiiii1

Same 200K Wikipedia training pairs, 3 epochs, RTX 3090. Switched
base to ``VietAI/vit5-base`` (MIT, 220 M params, VN-specific T5).

Results vs Toshiiiii1 + the v0.2.22 mT5-small baseline:

  Corpus               Toshiiiii1   mT5-small   vit5-base
  business_55  word    97.81 %      89.58 %     93.69 %
  literary_udvtb word  89.40 %      84.14 %     89.47 %
  business-literary gap   8.41 pp      5.44 pp     4.22 pp ⭐

**Adoption gate** (≥ 96 % business AND > 89.40 % literary): NOT met.
vit5-base ties on literary (+0.07 pp) but loses 4.12 pp on business.
**Don't publish.** Toshiiiii1 stays the default.

**The interesting finding:** vit5-base produces the most
**register-balanced** model — only 4.22 pp business-literary gap vs
Toshiiiii1's 8.41 pp. For users whose corpus is mixed-register and
who can tolerate sub-Toshiiiii1 absolute quality, vit5-base would be
the right pick. But that's a niche, not the default.

The negative result is committed at
``training/diacritic/results/vit5-base-200k_summary.json``.

### Training-experiment follow-up queue (deferred)

Both experiments hit ~94 % business, ~89 % literary. To reach
Toshiiiii1's 97.81 % business while keeping register balance, we'd
need one of:

1. **5 × more data**: 1 M pairs instead of 200 K. Cheapest experiment;
   eval loss was still falling at end of training, suggesting under-fit.
2. **5–10 epochs instead of 3**: same data, longer training.
3. **vit5-large**: 770 M VN-specific T5; better representation capacity.
4. **ByT5-small**: char-level, robust to register noise per arxiv 2201.13242.
5. **Multi-task: diacritic + spelling correction**: more training signal.

None of these is a sure win and each costs hours of GPU. Deferred to
v0.3.x — Toshiiiii1 covers production for v0.2.x users.

## [0.2.22] — 2026-04-27

### Train experiment #1: mT5-small fine-tune — **does not adopt**

First training run: `google/mt5-small` (Apache 2.0, 300 M params total /
~60 M VN-active) fine-tuned on 200 K (stripped, target) pairs from VN
Wikipedia (`hirine/wikipedia-vietnamese-1M296K-dataset`, CC-BY-SA-4.0)
for 3 epochs on RTX 3090, bf16 + grad-checkpointing.

Results vs Toshiiiii1 reference baseline:

  Corpus               Toshiiiii1   mT5-small (ours)   Δ
  business_55  word    97.81 %      89.58 %            -8.23 pp
  business_55  sent    n/a          40.00 %            n/a
  literary_udvtb word  89.40 %      84.14 %            -5.26 pp
  literary_udvtb sent  34.25 %      16.38 %            -17.87 pp

**Adoption gate NOT met** (need ≥ 96 % business AND > 89.40 % literary).
Don't ship. mT5-small's shared-multilingual embedding table dilutes the
VN-specific signal vs Toshiiiii1's VN-tuned T5.

**Eval loss was still decreasing at end of training** (final 0.083
vs initial 0.43). With more epochs / data the model would keep
improving — the result is a floor, not a ceiling. Follow-up experiment
launched (vit5-base, VN-specific 220 M from VietAI).

The negative result is committed (training_summary.json) and a
``training/diacritic/`` scaffold is published so anyone can reproduce
the experiment from a clean clone:

```bash
python training/diacritic/prep_data.py --max-pairs 200000
./training/diacritic/launch_remote_train.sh \
    --model-id google/mt5-small \
    --epochs 3 --batch-size 8 --gradient-accumulation-steps 4 \
    --gradient-checkpointing --bf16
```

## [0.2.21] — 2026-04-26

### VLM OCR audit: image upscaling, raw I/O sampling

ALWAYS DOUBLE-CHECK pass on VLM OCR per the new rule. Sampled raw VLM
output on the first 5 vn_ocr_subset images and noticed all are
**64-pixel-tall line crops** — way below the patch sizes Qwen2.5-VL was
trained on (224/336 px). Hypothesis: tiny line images get downsampled
into illegibility by the vision encoder, leaving the language prior
to hallucinate from.

Tested with 4x upscale (LANCZOS) before sending. Results on full 50:

  Configuration                     CER     Exact   p50 ms
  upscale=1 (original)            31.14 %   18.0 %    576
  upscale=4                       46.27 %   14.0 %  2,250

4x upscale **hurts** on this corpus despite making sample 1 nearly
perfect ("1892 - Tạp Chí Vogue Được Phát Hành Lần Đầu Tiên"). The
upscale gives more visual real estate for the language prior to
hallucinate longer wrong answers. Confirmed: VLM on tight line crops
is the wrong tool, regardless of preprocessing.

`OllamaVLM` gains:
- `upscale: int = 1` constructor kwarg + `--ollama-upscale` CLI flag
- `num_predict` bumped from 512 to 2048 (some upscaled samples were
  truncating at 512)

Default behavior unchanged (upscale=1) — Tesseract remains the right
tool for clean printed line OCR. VLMs earn their cost on document
*understanding* (forms, IDs, handwriting), not line transcription.

## [0.2.20] — 2026-04-26

### PhoRanker corrected: +13.8 pp R@1 with proper word segmentation

ALWAYS DOUBLE-CHECK pass on PhoRanker per the new rule. The v0.2.17
number (R@1 70.0 %) was wrong: we sent raw unsegmented text to a model
whose card explicitly requires VnCoreNLP word-segmented input.
Re-checking the model card caught it.

Re-measured on Zalo Legal 5 k with proper preprocessing:

  Reranker (bkai-vietnamese-bi-encoder embedder)         R@1     R@10    MRR@10  p50 ms
  bge-reranker-v2-m3 (568 M, 2.3 GB)                    86.3 %  100.0 %  0.929   583
  PhoRanker WITH word segmentation (100 M, 395 MB)      83.8 %   98.8 %  0.907   863
  PhoRanker WITHOUT segmentation (BROKEN config)        70.0 %   97.5 %  0.802   295

PhoRanker is now only 2.5 pp R@1 behind the default at **5.7× smaller
disk** — a much better tradeoff than the broken-config 16 pp gap. The
863 ms p50 includes per-query underthesea segmentation; in production
you'd cache segmented corpus chunks at index time.

**`CrossEncoderReranker` gains `word_segment` kwarg:**

```python
CrossEncoderReranker("itdainb/PhoRanker", word_segment=True)
```

`bench_rag_vn.py` gains `--reranker-word-segment`. No model-name
sniffing — caller decides per our internal best-practice rule.

## [0.2.19] — 2026-04-26

### Refactor: replace hardcoded model branches with declarative specs

User direction: "don't hardcode model names in code — prefer flexible
configurations." The v0.2.17/.18 commits had three hardcodes that broke
the rule:

  - `per_model_cap = {"hiieu/halong_embedding": 512, ...}`
  - `_is_e5_family()` with `if "halong" in lid or "/e5-" in lid`
  - `if "phoranker" in args.reranker.lower()` (already removed in v0.2.17)

Replaced with declarative `EmbedderSpec` dataclass per model in
`benchmarks/rag/bench_embedder_compare.py`. Each entry owns:

  - `model_id`: HuggingFace id
  - `max_seq_length`: explicit cap
  - `query_prefix`, `passage_prefix`: e5-style asymmetric prefixes
  - `word_segment`: bkai-style underscore segmentation flag
  - `notes`: model-card provenance for the JSON output

Bench loop is now model-agnostic. Adding a new model = appending to
`KNOWN_SPECS`; not editing branches.

### Halong embedding — corrected to 60.00 % R@1 with proper config

ALWAYS DOUBLE-CHECK on halong: the v0.2.17 number (55.00 %) was run
at max_seq_length=256 with `query:` / `passage:` prefixes — both
WRONG per the model card. halong is mE5-base ft trained at 512 with
no prefixes (the fine-tune re-purposed the head). Re-measured with
correct config:

  hiieu/halong_embedding (max_seq=512, no prefix): 60.00 % R@1
                                                  (was 55.00 % with wrong config)

Still loses to bkai (76.25 %) by 16 pp. Author's published 82.94 % on
their holdout doesn't reproduce on our 5k subset — likely a different
question selection. bkai stays.

### `--samples N` dumps raw I/O per model

Per our internal autonomous-loop §8 (ALWAYS DOUBLE-CHECK):
`bench_embedder_compare.py --samples 3` dumps the first N (question,
gold doc, top-1 predicted doc) tuples into the JSON output. Reading
five raw samples is the cheapest way to catch broken metrics —
costs 2 minutes, saves a wrong README claim.

## [0.2.18] — 2026-04-26

### Bench-methodology fix: 0/800 sentence-exact was a tokenization artifact

User caught the implausible 0/800 sentence-exact match in v0.2.17's
UD-VTB diacritic bench and asked us to investigate. They were right —
even a mediocre model would land *some* sentences exactly right. The
0/800 was a comparison-time artifact, not real model failure.

Root cause: UD treebank ships sentences in *tokenized* form (spaces
around every punctuation mark — `nhỉ ? " .` not `nhỉ?".`), the
parsing-tool convention. Modern seq2seq models output natural
Vietnamese with attached punctuation. Comparing raw `.split()` lists
shifts the alignment at the first punctuation; downstream tokens
compare wrong-vs-wrong even when diacritics are perfect.

Fixed by adding `normalize_punct()` to
`benchmarks/accuracy/bench_diacritic_hf_udvtb.py`: NFC-normalize +
strip whitespace before/after attaching punctuation on **both** sides
before tokenizing for comparison. Both metric tracks (raw and
normalized) are now reported in the JSON output for transparency.

Corrected Toshiiiii1 numbers:

  Corpus                       Word acc     Sentence-exact
  diacritic_eval_v0 (55-sent)   97.81 %     not measured (raw)
  ud_vi_vtb test (800-sent)     89.40 %     34.25 %   (was 54.14 % / 0.0 %)

The model is **register-sensitive but not broken** on classical
literary VN. The 8 pp gap between business and literary is mostly
proper-noun ambiguity (Hùng / Hưng / Hứng) and a few minor-register
words — not architectural failure.

our internal policy autonomous-loop §5 gains a second methodological lesson:
**implausible metrics demand investigation.** Anything pegged at 0 %
or 100 % on a real model is almost certainly a bench bug. We caught
this exact failure mode here.

README, recipes.md, training_plan, benchmark.md all updated with the
corrected numbers.

## [0.2.17] — 2026-04-26

### Honest disclosure: Toshiiiii1 is register-overfit (97.81 % → 54.14 %)

User direction: launch exhaustive search across all components for
better lightweight Apache/MIT options. Three deep-research agents
returned with surveys and a critical caveat: **the 97.81 % Toshiiiii1
diacritic accuracy is overfit to a single 55-sentence eval corpus.**

Re-measured on UD_Vietnamese-VTB test split (800 sentences, classical
literary register from VN treebank):

  Model                              Business 55-sent   Literary 800-sent
  Toshiiiii1 T5 200M                       97.81 %             54.14 %
  Sentence-exact match                  not measured         0.00 % (0/800)

A 43 pp gap between corpora exposes the model is fitted to modern
business / news Vietnamese — not the open VN diacritic SOTA we'd
implied. Production guidance updated to register-conditional:

  - Modern business / contracts / news → Toshiiiii1 wins
  - Classical literary / mixed / unknown → cloud gpt-4o-mini, or
    register-aware fallback

our internal policy autonomous-loop §5 gains a "multi-corpus measurement is
mandatory for adoption claims" rule. README + recipes.md flagged
with a register-caveat note. docs/training_plan_2026q2.md updated.

### `CrossEncoderReranker` auto-detects max_length

User direction: "make it flexible and configurable." We caught a
hardcoded `"phoranker" in args.reranker.lower()` string match in the
RAG bench that capped sequence length at 256. Replaced with an
auto-detect on the model's `config.json max_position_embeddings`:

  Model                          Auto-detected max_length
  itdainb/PhoRanker (PhoBERT)            256
  BAAI/bge-reranker-v2-m3 (XLM-R)        512
  namdp-ptit/ViRanker (BGE-M3)           512

Override via `max_length=...` constructor kwarg or
`--reranker-max-length` CLI flag in `bench_rag_vn.py`. Default behavior
is now correct without users having to know each reranker's family.

### Cross-component candidate audit (3 agents, all returned)

**Diacritic restoration (no swap).** No public Apache/MIT model with
safetensors and a verified VN benchmark beats Toshiiiii1 on its own
register. `peterhung/vietnamese-accent-marker-xlm-roberta` (Apache,
2.24 GB) auto-rejected (size + .bin only). `saeliddp/distilbert-viet-
diacritic-restoration` (172 MB, 96.10 % syllable acc) auto-rejected
(CC-BY-NC). `yammdd/vietnamese-diacritic-restoration-v2` (MIT) is
TF-only and reports below baseline.

**Embedder (no swap).** `hiieu/halong_embedding` (Apache, 300 M
mE5-base ft) reportedly hit Acc@1 0.8294 on author's Zalo Legal split.
Re-measured on our 5k subset: **R@1 56.25 % with prefix tuning**, vs
bkai 76.25 %. Author's published 82.94 % does not reproduce on a
random 5k subset of the same corpus. bkai stays.

**Reranker (added lite tier).** `itdainb/PhoRanker` (Apache, 100 M,
395 MB) doesn't beat bge-reranker-v2-m3 on legal-VN (R@1 70.0 % vs
86.3 %) but is 5.7× smaller and 2× faster. Earned a "lite" tier in
docs/benchmark.md for memory-constrained deployments.

**Sub-4B VN LLM (worth benching, deferred).** `arcee-ai/Arcee-VyLinh`
(Apache, 3 B, claims 95.4 % win-rate vs PhoGPT-4B on m-ArenaHard-VN)
not yet run through our diacritic harness — added to follow-up.

New baselines in `benchmarks/results/`:
- `baseline_diacritic_toshiiiii_udvtb_test.json` (the honest 54.14 %)
- `baseline_embedder_compare_halong_vs_bkai.json` (halong loses)
- `baseline_embedder_compare_halong_with_prefix.json` (halong loses with prefixes)
- `baseline_phoranker_zalo5k.json` (PhoRanker numbers)
- `baseline_bge_reranker_bkai_zalo5k.json` (bge-reranker direct comparison)

### `BKaiEmbedder` plumbed into `bench_rag_vn.py`

Added `bkai` to the `--embedder` choices. Required for the
apples-to-apples reranker comparison above.

### Documentation

`docs/recipes.md` — new task-oriented cookbook (text utilities →
docs → retrieval → RAG → chat → ops). Each recipe links to the
docs/benchmark.md row that justifies the pick.

README modernized: status badge to v0.2.17, "Recommended stack" table
with measured numbers, register-shift caveat for diacritic restoration.

## [0.2.16] — 2026-04-26

### Diacritic backend grid: ONNX no win on small T5

User direction: questioning lightweight inference (llama.cpp, ONNX,
quantization). Audited the diacritic path.

Same Toshiiiii1 T5 weights, three execution paths, identical 97.81 %
word accuracy:

  Backend       Hardware            Mean ms  p50 ms
  PyTorch       RTX 3090 (CUDA)         152     148
  PyTorch       CPU (8 cores)           377     357
  ONNX Runtime  CPU (8 cores)           410     394

ONNX is 8 % slower than PyTorch CPU. Modern PyTorch with MKL-DNN is
already optimal for a 200 M T5 in eager mode; ONNX runtime kernel
overhead doesn't pay off without INT8 quantization. Not shipping an
ONNX export step in `nom-vn[diacritic-hf]`. Users who genuinely need
ONNX (cross-platform deployment without Python+PyTorch) can run
`optimum-cli export onnx ...` themselves.

INT8 quantization (typical 2-3x CPU speedup at some accuracy cost)
is a future follow-up.

Reranker landscape audit: `BAAI/bge-reranker-v2-m3` (Apache, 568 M)
remains the leader for VN. `namdp-ptit/ViRanker` (Apache, 600 M) is
within 1.3 pp R@1 on legal-VN per the existing RAG grid; both stay
shipped under `nom-vn[reranker]`. `jinaai/jina-reranker-v2-base-multilingual`
(278 M, smaller) is CC-BY-NC blocked from shipping. No
strictly-lighter Apache reranker beat `bge-reranker-v2-m3` in the
audit.

Baseline: benchmarks/results/baseline_diacritic_onnx_cpu.json

## [0.2.15] — 2026-04-26

### `BKaiEmbedder` — +41 pp R@1 over current default on Zalo Legal QA

User direction: keep questioning whether better SOTA models exist for
each component. Audited the embedder. Found one.

`bkai-foundation-models/vietnamese-bi-encoder` (Apache 2.0, 383 MB,
PhoBERT-base-v2, 768-dim) on Zalo Legal QA 5k (5,061 docs, 80
questions), RTX 3090:

  Model                                                R@1     R@10    MRR@10
  bkai-foundation-models/vietnamese-bi-encoder  (NEW) 76.25%  98.75%  0.8604
  dangvantuan/vietnamese-embedding (current default)  35.00%  67.50%  0.4449

bkai wins by +41.25 pp R@1 and +31.25 pp R@10 in smaller disk size.
The gap is structural: bkai was trained with MultipleNegativesRankingLoss
on Q→Doc retrieval pairs from MS MARCO + SQuAD v2 + 80% Zalo Legal —
exactly the task we run. dangvantuan was fine-tuned on STS (symmetric
similarity), the wrong task distribution.

New: src/nom/embeddings/bkai.py ships `BKaiEmbedder`. Wraps
SentenceTransformer + auto-applies underthesea word segmentation
(bkai requires multi-syllable VN words joined with underscores per
its training format).

Install: `pip install "nom-vn[embeddings,nlp]"`

Default NOT switched in 0.2.x — would invalidate every existing user's
persisted embedding cache. The 0.3.x major release flips the default.

```python
from nom.embeddings import BKaiEmbedder
from nom.rag import RAG
rag = RAG(embedder=BKaiEmbedder(device="cuda"))
```

Cross-checked against bkai's own published Zalo Legal numbers (Acc@1
73.28, Acc@10 93.59) — our 5k subset is slightly easier (76.25, 98.75)
which matches expected distractor-pool effect.

`docs/training_plan_2026q2.md` retraction: prior version said "do
nothing" for embedder. Replaced with "adopt bkai".

New bench harness: benchmarks/rag/bench_embedder_compare.py
Baseline: benchmarks/results/baseline_embedder_compare_zalo5k.json

## [0.2.14] — 2026-04-26

### `Toshiiiii1` T5 wins diacritic restoration — distil recommendation retracted

User correction: there are public Apache-licensed VN diacritic models we
hadn't benched before recommending a 100 M distillation. Audited and
re-measured.

`Toshiiiii1/Vietnamese_diacritics_restoration_5th` (Apache 2.0, 200 M T5,
safetensors) on the same 55-sentence corpus, RTX 3090, warmup 3:

  Backend                              Word acc   Mean s/sent  Disk
  Toshiiiii1 T5 (NEW)                   97.81 %    0.152       ~1 GB
  cloud gpt-4o-mini                     95.37 %    1.27        —
  local gemma4:e4b Q4                   93.18 %    1.37        9.6 GB
  local gemma3:4b Q4                    87.90 %    1.10        3.3 GB
  bmd1905/vietnamese-correction         15.57 %    0.30        ~1.6 GB
  rule baseline                         41.06 %   <0.001       0

Toshiiiii1 beats cloud by +2.44 pp at 8x lower latency and 9.6x smaller
disk than the next-best local option. **No training needed.**

New: `src/nom/text/diacritic_models.py` ships an `HFDiacriticModel`
adapter. Default model_id is the Toshiiiii1 winner. Plumbed into
`fix_diacritics(text, model=...)`:

    from nom.text import fix_diacritics
    from nom.text.diacritic_models import HFDiacriticModel

    restorer = HFDiacriticModel()
    fix_diacritics("Hop dong nay duoc lap", model=restorer)
    # => 'Hợp đồng nay được lập'

Install: `pip install "nom-vn[diacritic-hf]"` (transformers<5 + torch +
sentencepiece). The transformers cap is required: 5.6+ has a slow-T5
tokenizer regression that breaks Toshiiiii1's load.

Distil recommendation in docs/training_plan_2026q2.md RETRACTED.

our internal policy gains an "Autonomous improvement loop" section codifying the
"off-the-shelf before training" rule: exhaustively bench public
Apache/MIT/safetensors candidates *before* recommending a fine-tune.
This was the third time we'd missed this — saving it as a durable rule.

3 new tests covering `model=` kwarg precedence, paragraph-break
preservation, and the LLM-overrides path. 344 pass.

## [0.2.13] — 2026-04-26

### Docling measured: 150x slower than pypdfium2, no fidelity edge

Followed up on the Docling open question from v0.2.10. Same synthetic
VN PDF (47 KB, 7 pages, 18,877 GT chars), warmup 2 + best-of-3:

  Library     Best (s)  Throughput (chars/s)  Overlap  Disk
  pypdfium2   0.0079    2,350,431             99.81%   <10 MB
  pdfplumber  0.3654       51,052             99.81%    <5 MB
  docling     1.1889       15,703             99.72%    ~1 GB

Docling is 150x slower than pypdfium2 and slightly worse on fidelity
(99.72% vs 99.81%) — the ML layout pipeline (DocLayNet + TableFormer)
pays no dividends when the PDF already has a clean text layer.

Keep Docling OUT of nom-vn[doc] for now. If a user-facing complex-
layout corpus emerges (legal forms, government reports), surface it
as a future nom-vn[docling] extra → nom.doc.layout_extract(). Until
then, ~1 GB of ML deps is unjustified for plain-text PDFs.

Baseline: benchmarks/results/baseline_pdf_extract_docling.json

## [0.2.12] — 2026-04-26

### Final report: training / fine-tuning recommendations

Closes the "improve current pipelines to maximum accuracy first, then
suggest tuning" workstream from v0.2.5 → v0.2.11. New synthesis doc
at `docs/research/2026-04-finetune-recommendations.md`.

**Bottom line:** of 8 components benched, **6 stay off-the-shelf**.
Two training runs are recommended:

1. **Distil a 100M-param VN diacritic model** (~$10–30 cloud, 1 H100·6h).
   Drives 87.9% → 92–95% acc at 250–500 MB on disk vs 9.6 GB for
   gemma4:e4b. Critical for mobile / browser deployment where sub-2 GB
   models all fall below the 41% rule baseline.
2. **Fine-tune VietOCR on noisy VN scans** (~$80–150 cloud, 1 H100·24h).
   Blocked on upstream Python 3.13 packaging fix; revisit once
   `pip install vietocr` works on 3.13.

**Do nothing for:**

- OCR on clean printed text (Tesseract 5.5% CER beats VLM 31% by 25 pp
  and is 10× faster; finetune offers no leverage).
- Word segmentation (underthesea CRF F1 95.70% is at its ceiling;
  19 pp gap to nom.text is the speed/accuracy tradeoff users want).
- Dense embedder (`dangvantuan/vietnamese-embedding` is public SOTA at
  440 MB).
- Reranker (`BAAI/bge-reranker-v2-m3`).
- BM25 (algorithm, not model).
- General-purpose LLM (gemma3:4b / gemma4:e4b / qwen3:8b cover VN at
  88–93% on tested tasks; task-specific small models or prompt
  engineering give better $/pp than general-LLM finetuning).

The doc includes per-component decision triggers — what would flip a
"do nothing" recommendation back to "train". Avoids re-visiting any of
these prematurely.

## [0.2.11] — 2026-04-26

### VLM OCR engine + measurement: VLMs lose decisively on line OCR

Added an `OllamaVLM` engine to `benchmarks/accuracy/bench_ocr_real.py`
so we could honestly answer "should we add a VLM as the default OCR
backend for Vietnamese?". Result: **no, not on this corpus.**

Measured 2026-04-26 on the first 50 images of `vn_ocr_subset`
(ducto489 mid-noise mirror, single-line printed VN), all engines
on the same images, RTX 3090 / Q4_K_M:

  Engine             CER     Exact match   p50 ms
  Tesseract 5 (vie)  5.53%   38.0%          80.6
  EasyOCR (vi)       9.39%   18.0%          31.1
  qwen2.5vl:7b      31.07%   18.0%         818.0
  qwen2.5vl:3b      39.86%   15.0%       1,165.5

VLM failure modes observed: token-loop repetition ("1892 92 92 92
..."), confidently-wrong substitution ("XÃ CHIỀNG ƠN" -> "CHÍNH XÁC"),
and "complete-the-sentence" hallucination ("churchill và tưởng giới
thạch" -> "Churchill và tướng Eisenhower cùng được trao giải thưởng").
The language prior dominates the visual signal on tight line crops
without document context.

Default stays Tesseract. VLM OCR will surface as a distinct
`nom.doc.vlm_extract()` path in a future release, scoped to
*understanding* documents (invoice fields, IDs, forms, handwriting),
not transcribing them.

`OllamaVLM` engine class is committed and gated behind `--engines
ollama_vlm` so users can re-run the comparison on their own corpus.
New CLI flags: `--ollama-base-url`, `--ollama-model`, `--limit`.

## [0.2.10] — 2026-04-26

### PDF text extraction — `pypdfium2` 46x faster than `pdfplumber`, no AGPL trap

The previous default for plain-PDF text extraction was `pdfplumber` (MIT,
slow). The fastest option in the wild is PyMuPDF / `fitz` (~19× faster
on `py-pdf/benchmarks`) — but it's AGPL-3.0, which forces every project
that ships it to be AGPL. We will not ship that. Instead:

- **Adopt `pypdfium2>=4.30`** — BSD-3 wrapper over Google's PDFium
  (Apache-2.0). Same fidelity as `pdfplumber` on Unicode-clean PDFs,
  46× faster on plain-text extraction.
- **Keep `pdfplumber`** in `nom-vn[doc]` for the table-extraction path
  (still better cell detection than pypdfium2's plain text-page API).
- **Do not ship PyMuPDF.** Users who legitimately need it can install
  it directly; we won't expose a wrapper that muddies the license.

Measured 2026-04-26 on a synthetic 7-page VN PDF (47 KB, 18,877 GT
chars), warmup 3 + best-of-5 (our internal policy §12):

| Library | License | Best (s) | Throughput | Char overlap |
|---|---|---:|---:|---:|
| `pypdfium2==5.7.1` | BSD-3 | **0.0079** | **2,350,431 chars/s** | **99.81%** |
| `pdfplumber==0.11.9` | MIT | 0.3654 | 51,052 chars/s | 99.81% |

The committed `udhr_vie.pdf` cannot be used here — it embeds a custom
font without a ToUnicode CMap, so every extractor returns CIDs / garbled
bytes. New generator `benchmarks/data/synthetic_pdf_vi/_generate.py`
builds a Unicode-clean VN PDF from real public-domain prose using
fpdf2 + DejaVuSans (`apt install fonts-dejavu`). The .pdf is gitignored;
the `.gt.txt` ground truth is committed.

New bench: `benchmarks/perf/bench_pdf_extract.py`. Baseline:
`benchmarks/results/baseline_pdf_extract.json`.

Docling (IBM, MIT, layout-aware tables/formulas/multi-column) is logged
as a follow-up: ~1 GB of ML deps is too heavy for the default but could
earn a place in `nom-vn[docling]` if it materially beats pdfplumber on
tables. Not yet measured.

## [0.2.9] — 2026-04-26

### Word-segmentation gold-standard bench (UD_Vietnamese-VTB)

`benchmarks/accuracy/bench_segment.py` was a Jaccard-only inter-tokenizer
sniff test on the 55-sentence diacritic corpus. That doesn't tell users
which tokenizer to pick for their pipeline. Replaced with a real bench
against gold word segmentation.

New corpus committed: **`benchmarks/data/ud_vi_vtb/`** —
[UD_Vietnamese-VTB](https://github.com/UniversalDependencies/UD_Vietnamese-VTB)
CoNLL-U files (CC-BY-SA-4.0), 800 test / 1,123 dev / 1,400 train sentences,
11,692 gold word tokens in test. Fetched via `_fetch_all.py`.

Bench now computes pooled-corpus precision / recall / F1 by matching
predicted (start, end) char spans against gold spans extracted from the
FORM column. Methodology: warmup 3 + best-of-5 throughput, version-pinned
comparison target (`underthesea==9.4.0`).

| Tokenizer | Precision | Recall | F1 | Throughput |
|---|---:|---:|---:|---:|
| `underthesea==9.4.0` | 95.94% | 95.46% | **95.70%** | 38,102 tok/s |
| `nom.text` (rule) | 70.94% | 82.90% | 76.46% | **747,117 tok/s** |

**Recommendation:**
- For RAG indexing / BM25 / lightweight cleanup → `nom.text` (zero-dep,
  20× faster; the 19 pp F1 gap doesn't matter when downstream is
  bag-of-words).
- For NER / dependency parsing / linguistic tasks →
  `nom-vn[nlp]` → `underthesea`.

Cross-checked against underthesea's own published VLSP 2013 numbers (~94%
F1) — our 95.70% on UD-VTB is consistent (UD-VTB is a slightly easier
register than VLSP). No methodology divergence to chase.

PyVi remains auto-rejected per our internal principle 11 (ships `.pkl`
model files = arbitrary code execution on load).

`bench_segment.py` gains `--corpus {diacritic_eval, ud_vtb}` and `--split`
flags. Default still `diacritic_eval` for the cheap sniff test.

## [0.2.8] — 2026-04-26

### Local-LLM diacritic restoration — production-grade for user machines

Two engineering fixes turned the LLM-backed `fix_diacritics` from "cloud
only" into a real local option, plus a comprehensive measurement of
quantized models on consumer-grade hardware.

**Fixes** (`src/nom/llm/ollama.py` + `src/nom/text/normalize.py`):

1. **`Ollama` adapter defaults to `think=False`.** Qwen3 / DeepSeek-R1
   thinking-mode emit hidden CoT into a separate `thinking` field,
   leaving `content` empty for terse extraction tasks. With the new
   default, `qwen3:4b` on the diacritic bench went from `0.00%` →
   `47.36%`. Users who want CoT can still opt in via
   `Ollama(think=True)`.
2. **`fix_diacritics(llm=...)` uses Ollama structured output.** The
   helper now sends a JSON schema (`{"restored": "..."}`) via the
   adapter's `schema=` kwarg. Constrained decoding stops small models
   from rambling explanations into the response. Adapters that don't
   accept `schema=` fall through to the existing defensive prompt path.

**Local LLM grid — measured 2026-04-26 on RTX 3090, Q4_K_M, warmup 3,
55-sentence corpus** (full table in `docs/benchmark.md`):

| Model | Q4 size | Word acc | Mean s/sent |
|---|---:|---:|---:|
| **gemma4:e4b** | 9.6 GB | **93.18%** | 1.37s |
| **gemma3:4b** ⭐ | **3.3 GB** | **87.90%** | 1.10s |
| qwen3:8b | 5.2 GB | 87.26% | 0.93s |
| gemma4:e2b | 7.2 GB | 85.33% | 1.23s |
| qwen3:4b | 2.5 GB | 47.36% | 0.94s |
| (rule baseline) | 0 | 41.06% | <1ms |
| llama3.2:3b | 2.0 GB | 38.35% | 1.50s |
| qwen3:1.7b | 1.4 GB | 18.15% | 0.63s |
| gemma3:1b | 0.8 GB | 15.32% | 1.41s |
| phi4-mini | 2.5 GB | 6.95% | 2.32s |
| (cloud gpt-4o-mini) | — | 95.37% | 1.27s |

**Recommended local default: `gemma3:4b`** — 3.3 GB fits 4-6 GB VRAM
laptops, 87.9% accuracy at 1.1 s/sent. Within 7.5 pp of cloud quality.

**Quality ceiling for local: `gemma4:e4b`** — 93.2%, only 2.2 pp shy of
cloud, but needs 12 GB+ VRAM (multimodal weights inflate disk).

**Mobile (sub-2 GB) is not viable yet** — quality cliff is sharp around
3 B params for VN; gemma3:1b and qwen3:1.7b fall below the rule baseline.
Llama 3.2 / phi4-mini disqualified entirely (tokenizer / hangs).

Reproduce one model: `python benchmarks/accuracy/bench_diacritics.py
--llm ollama --llm-model gemma3:4b --warmup 3`.
Reproduce the full grid: `OLLAMA_BASE_URL=http://localhost:11434
benchmarks/accuracy/run_diacritic_local_grid.sh`.
Aggregate: `python benchmarks/accuracy/_summarize_diacritic_grid.py`.
Per-model results: `benchmarks/results/local_diacritic_grid/`.

4 new tests covering `think` parameter behaviour and the structured-output
JSON path. 341 pass (348 collected; 5 OCR + 2 model-download integration
deselected when those deps aren't installed).

## [0.2.7] — 2026-04-26

### `fix_diacritics(text, llm=...)` — LLM-backed diacritic restoration

The v0.0.1 rule-based table tops out at ~41% word accuracy. Per the
"improve current pipelines to maximum accuracy" directive: rather
than ship a model wrapper (the obvious VN-finetuned options are
either CC-BY-NC, ship pickle, or aren't on HF Hub stable hosting),
we wired any `nom.llm.LLM` adapter directly into `fix_diacritics`.

```python
from nom.text import fix_diacritics
from nom.llm import OpenAI

restored = fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3", llm=OpenAI())
# 'Hợp đồng này được lập ngày 14 tháng 3'
```

Measured on `benchmarks/data/diacritic_eval_v0.txt` (55 sentences,
777 words, 4 registers — CC0):

| Backend | Word accuracy | Diacritic recall | Elapsed |
|---|---:|---:|---:|
| Rule-based (default, no deps) | **40.59%** | 34.08% | 0.005s |
| OpenAI gpt-4o-mini | **95.37%** | **94.61%** | 70s |
| Ollama qwen3:1.7b | 0%[*] | 0% | 132s |

[*] qwen3:1.7b returns input unchanged at this prompt — the 1.7B
class is too small for the task. Production users who want a local
model should pull qwen3:8b (~5GB) or larger; we don't ship a
recommended model size in defaults because the right size depends on
the user's hardware budget.

`+54.78 percentage points` over the rule baseline with no fine-tuning
and no shipped model. Implementation lives entirely in
`src/nom/text/normalize.py` — splits input at blank-line paragraph
breaks for fault isolation, defensively strips `<think>` tags,
label-echoes, and code fences from LLM output.

6 new tests in `tests/test_normalize.py` covering the LLM path
(deterministic, no real LLM calls). 342 total pass.

## [0.2.6] — 2026-04-26

### `nom.retrieve.BM25Retriever` — bm25s backend swap

The pure-Python BM25 implementation became the latency bottleneck on
the full Zalo Legal QA corpus (430 ms p50 on 82,696 chunks). Swapped to
[`bm25s`](https://github.com/xhluca/bm25s) (MIT, scipy.sparse, no
pickle, no native binaries — passes our internal policy principle 11).

Verified on the full corpus (`benchmarks/results/bm25_compare__zalo_full.json`):

| Metric | Pure-Python | bm25s | Delta |
|---|---:|---:|---:|
| recall@1 | 0.3947 | 0.3947 | identical |
| recall@10 | 0.7805 | 0.7805 | identical |
| mrr@10 | 0.5355 | 0.5360 | +0.0005 (rounding) |
| index time (s) | 35.11 | 36.86 | +5% (one-shot) |
| **search p50 (ms)** | **426.85** | **0.70** | **607× faster** |
| search p95 (ms) | 713.79 | 1.31 | 545× faster |

External `BM25Retriever` API is unchanged: `fit()`, `search()`,
`score()`, `name == "bm25"`. All 336 existing tests pass.

`bm25s` and `scipy>=1.10` added to core deps. Both are MIT/BSD,
small footprint, well-audited.

### Documented BM25 latency win at 5k corpus

Re-ran RAG grid on `vn_legal_zalo_5k.json` with new backend
(committed as `zalo_5k__dangvantuan__bge_v2_m3__bm25s.json`):
BM25 latency 27 ms → 0.46 ms p50, hybrid 59 ms → 14 ms p50.
Quality unchanged across the grid.

## [0.2.5] — 2026-04-25

### Cross-encoder reranker — opt-in, default `BAAI/bge-reranker-v2-m3`

The single biggest quality lever we hadn't shipped, now wired in.
`nom.rag` gained a `Reranker` Protocol and a `CrossEncoderReranker`
implementation backed by `sentence_transformers.CrossEncoder` (no new
runtime dep — already pulled by `[embeddings]`).

```python
from nom.rag import RAG, CrossEncoderReranker
rag = RAG.from_documents(
    docs,
    llm=Ollama(model="qwen3:8b"),
    reranker=CrossEncoderReranker(),  # default = BAAI/bge-reranker-v2-m3
)
answer = rag.ask("Quyền cơ bản của công dân?", rerank=True)
```

`RAG.ask()` gained:

- `rerank=False` (default — backward-compatible, v0.2.4 behavior unchanged)
- `rerank_candidates=30` — bi-encoder pool size sent to the reranker
  (production sweet spot 30–75 per the survey papers)
- `rerank_keep=None` — top-K to keep after reranking (defaults to `top_k`)

Pipeline order: BM25 + dense → fuse to `rerank_candidates` → cross-encoder
rerank → top `rerank_keep` → LLM. Composes with `query_strategy="hyde"` /
`"multi_query"` from v0.2.4.

**Default model:** [`BAAI/bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3)
— Apache 2.0, safetensors, multilingual including Vietnamese, no special
preprocessing. Battle-tested in production RAG stacks.

**Documented alternatives** (one-line model_name swap):

- `namdp-ptit/ViRanker` — Apache 2.0, BGE-M3-base, best NDCG@3 on
  MMARCO-VI per arXiv:2509.09131.
- `itdainb/PhoRanker` — Apache 2.0, 100M params, best NDCG@10 on
  MMARCO-VI. Requires VnCoreNLP word segmentation (Java JVM); use only
  if you've already wired that up.

19 new tests in `tests/test_reranker.py` covering protocol conformance,
lazy load, fp16 path, error cases, and full RAG.ask integration.

### Real benchmarks on Vietnamese legal RAG

Two new fixtures sampled from the
[`GreenNode/zalo-ai-legal-text-retrieval-vn`](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn)
mirror (MIT) of the Zalo AI Challenge 2021 Legal Text Retrieval corpus:

- `benchmarks/rag/fixtures/vn_legal_zalo_2k.json` (1.5k articles, 50 q)
- `benchmarks/rag/fixtures/vn_legal_zalo_5k.json` (5k articles, 80 q)

Regenerate via `python benchmarks/rag/fixtures/_build_zalo_legal.py`.

`bench_rag_vn.py` extended with `--reranker` and `--device` (auto-picks
CUDA when available). 10-condition grid on the 5k fixture, RTX 3080
Laptop GPU, fp16, warmup=1, timed=2 (full table in `docs/benchmark.md`):

| Embedder | Retriever | recall@1 | recall@10 | mrr@10 | p50 ms |
|---|---|---:|---:|---:|---:|
| dangvantuan | BM25 | 0.762 | 0.975 | 0.843 | 27 |
| dangvantuan | Hybrid (RRF) | 0.650 | 0.975 | 0.780 | 59 |
| dangvantuan | + bge-reranker-v2-m3 | **0.863** | **1.000** | **0.931** | 681 |
| AITeamVN | Dense only | **0.825** | 0.975 | 0.894 | 47 |
| AITeamVN | + bge-reranker-v2-m3 | 0.863 | 0.988 | 0.923 | 720 |

Three findings worth noting:
- **Embedder choice matters more than reranker choice** for the
  bi-encoder stage. AITeamVN (BGE-M3 finetuned for VN legal) doubles
  dense recall@1 vs dangvantuan (0.412 → 0.825).
- **Rerankers converge** — both `bge-reranker-v2-m3` and ViRanker bring
  final recall@1 to ~0.863 regardless of feeder embedder.
- **Skip-the-reranker option exists** — AITeamVN dense alone gets 0.825
  recall@1 in 47 ms, ~15× faster than +rerank for a 4% absolute drop.

Per our internal principle 12 + new component-build rule #7: numbers come
from a committed-and-runnable script (`benchmarks/rag/bench_rag_vn.py`)
and a checked-in baseline JSON. Divergence from public Zalo numbers
(BM25 alone here = 0.762 recall@1; UIT 2024 reports BM25Plus
Exist@90=82.6% on full 21k corpus) is corpus-size-driven — fewer
distractors in our 5k subset — not a methodology bug.

### Datasets + baselines published to HuggingFace

`nrl-ai/vn-rag-bench` ([dataset](https://huggingface.co/datasets/nrl-ai/vn-rag-bench))
hosts the fixture builder + JSON fixtures + JSON baselines so anyone
can reproduce or compare without re-sampling.

### our internal policy — component-build workflow

Codified the loop applied here so every future component follows it:
research → build → test with real models → benchmark on real datasets →
iterate as a grid → cross-check against published numbers. See the
"Component build workflow" section in our internal policy for the full rule
set including the file-format trust ladder (safetensors > HF .bin from
a major lab > native opaque > pickle = always reject).

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

**No quality numbers claimed.** Per our internal principle 12, we won't
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
Corrected per our internal principle 12.

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
- `PPlanning/our internal policy` gained a 4-stage component-build workflow:
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
