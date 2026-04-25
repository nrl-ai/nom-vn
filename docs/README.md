# Documentation

Deeper documentation for **nom-vn**. The repo-root files (`README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`) cover the basics; this directory holds the design and benchmark detail.

## Index

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — the single-library design, submodule layout, and component picks (lightweight, fast, accurate, local, replaceable per-axis).
- **[PIPELINE.md](PIPELINE.md)** — the doc-extraction pipeline end-to-end. Per-stage picks, citations, the planned API surface.
- **[BENCHMARK.md](BENCHMARK.md)** — measured numbers per module + research-backed component selection. Reproducibility contract.

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
