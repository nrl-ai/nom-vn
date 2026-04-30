# Documentation

Deeper documentation for **nom-vn**. The repo-root files (`README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`) cover the basics; this directory holds the design and benchmark detail.

## Per-task pages

The primary structure: one consolidated page per user-facing task,
covering public landscape + our pipeline + trained models + datasets +
results + reproduction. Each page follows
[`tasks/_template.md`](tasks/_template.md) so the reader navigates any
page after learning one.

| Task | Status | Page |
|---|---|---|
| Diacritic restoration | shipped | [`tasks/diacritic-restoration.md`](tasks/diacritic-restoration.md) |
| Spell correction | in progress | _coming — alongside the spell-correction training track_ |
| Word segmentation | shipped | _to migrate_ |
| Embedding | shipped | _to migrate_ |
| Retrieval (BM25 + dense) | shipped | _to migrate_ |
| Reranker | shipped | _to migrate_ |
| OCR | shipped | _to migrate_ |
| PDF text extraction | shipped | _to migrate_ |
| Chunking | shipped | _to migrate_ |
| LLM chat | shipped | _to migrate_ |

The numbers + landscape detail for the not-yet-migrated tasks live in
[`benchmark.md`](benchmark.md) for now and are progressively being
moved into per-task pages.

## Cross-cutting docs

- **[architecture.md](architecture.md)** — the single-library design, submodule layout, and component picks (lightweight, fast, accurate, local, replaceable per-axis).
- **[pipeline.md](pipeline.md)** — the doc-extraction pipeline end-to-end. Per-stage picks, citations, the planned API surface.
- **[recipes.md](recipes.md)** — task-oriented "I want X, do Y" cookbook with copy-paste code.
- **[benchmark.md](benchmark.md)** — measured numbers per module + research-backed component selection. Being migrated to the per-task pages.
- **[datasets.md](datasets.md)** — Vietnamese benchmark corpora shipped under `benchmarks/data/`, plus the public `nrl-ai/*` datasets we publish on HF.
- **[release.md](release.md)** — how to cut a PyPI release (Trusted Publishing via GitHub Actions).
- **[sota_vn_2026q2.md](sota_vn_2026q2.md)** — current LLM, embedding, and OCR picks with verified citations. Deprecating; per-task pages are the live source.
- **[oss_landscape_2026q2.md](oss_landscape_2026q2.md)** — wider OSS Vietnamese AI ecosystem. Deprecating; per-task pages are the live source.
- **[training_plan_2026q2.md](training_plan_2026q2.md)** — when to fine-tune vs adopt off-the-shelf, per component.
- **[research/](research/)** — gitignored working notes (data audits, market scans). Per-claim citations land in per-task pages once distilled.

## Where things go

| File | Lives at | Why |
|---|---|---|
| `README.md`, `README.vi.md` | repo root | GitHub auto-renders; first thing new visitors see; bilingual peers — both update in lockstep when content changes |
| `LICENSE` | repo root | toolchain + license-detection convention |
| `CHANGELOG.md` | repo root | GitHub releases auto-pick this up |
| `CONTRIBUTING.md` | repo root | GitHub auto-surfaces this on PR/issue creation |
| Per-task user-facing detail | `docs/tasks/<name>.md` | one consolidated page per task |
| Cross-cutting design / pipeline | `docs/<topic>.md` | discoverable by humans; not in GitHub's "first look" path |
| Auto-generated API docs | `docs/api/` (planned, v0.2+) | populated by Sphinx/mkdocs in CI |

## Filename convention

Lowercase under `docs/` — except for the well-known repo-level files
GitHub auto-recognizes (`README.md`, `LICENSE`, `CHANGELOG.md`,
`CONTRIBUTING.md`). New per-task pages live as `tasks/<task-name>.md`.

## Coming later

- `docs/api/` — auto-generated module reference once the public surface stabilizes
- `docs/tutorials/` — task-driven walkthroughs (contract extraction, OCR cleanup, etc.)
- `docs/migration/` — version-to-version migration notes when we hit a breaking release
