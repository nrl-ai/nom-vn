# Documentation

Deeper documentation for **nom-vn**. The repo-root files (`README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`) cover the basics; this directory holds the design and benchmark detail.

## Index

- **[architecture.md](architecture.md)** — the single-library design, submodule layout, and component picks (lightweight, fast, accurate, local, replaceable per-axis).
- **[pipeline.md](pipeline.md)** — the doc-extraction pipeline end-to-end. Per-stage picks, citations, the planned API surface.
- **[benchmark.md](benchmark.md)** — measured numbers per module + research-backed component selection. Reproducibility contract.
- **[datasets.md](datasets.md)** — Vietnamese benchmark corpora shipped under `benchmarks/data/`, license per folder.
- **[sota_vn_2026q2.md](sota_vn_2026q2.md)** — current LLM, embedding, and OCR picks with verified citations.
- **[oss_landscape_2026q2.md](oss_landscape_2026q2.md)** — wider OSS Vietnamese AI ecosystem.
- **[research/](research/)** — deeper research notes (data audits, market scans). Every claim cited per CLAUDE.md rule.
  - **[research/data_sources_vn_2026q2.md](research/data_sources_vn_2026q2.md)** — master index of every Vietnamese data source we've found (text, OCR, speech, eval, pretraining), with status tags + citations. Start here when scoping data work.
  - **[research/ocr_training_data_vn_2026q2.md](research/ocr_training_data_vn_2026q2.md)** — what's actually shippable for VN OCR training, license-by-license + cost estimates.

## Where things go

| File | Lives at | Why |
|---|---|---|
| `README.md`, `README.vi.md` | repo root | GitHub auto-renders; first thing new visitors see |
| `LICENSE` | repo root | toolchain + license-detection convention |
| `CHANGELOG.md` | repo root | GitHub releases auto-pick this up |
| `CONTRIBUTING.md` | repo root | GitHub auto-surfaces this on PR/issue creation |
| Architecture / design / benchmark detail | `docs/` | discoverable by humans; not in GitHub's "first look" path |
| Auto-generated API docs | `docs/api/` (planned, v0.2+) | populated by Sphinx/mkdocs in CI |

## Coming later

- `docs/api/` — auto-generated module reference once the public surface stabilizes
- `docs/tutorials/` — task-driven walkthroughs (contract extraction, OCR cleanup, etc.)
- `docs/migration/` — version-to-version migration notes when we hit a breaking release
