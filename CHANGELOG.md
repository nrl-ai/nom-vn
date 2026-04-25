# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for v0.0.2
- **Replace the rule-based `fix_diacritics` table with an ML-backed path.**
  Add `backend="model"` option that wraps an existing high-accuracy diacritic
  restoration model (PyVi or a DistilBERT-based HuggingFace model). The
  ~120-entry rule table stays as the zero-dep fallback (`backend="rules"`).
  Target: jump from ~41% baseline to ~90%+ word accuracy on the public corpus.
- Add `nom.text.tokenize()` and `nom.text.sentence_split()`.
- Add `nom.text.is_diacritic_correct()` to detect misplaced tone marks.
- Add optional dependencies group: `pip install nom-vn[diacritics]`.

### Planned for v0.1.0
- `nom.doc.extract()` — real implementation: `pdfplumber`/`pymupdf` for PDFs,
  `pytesseract` for scans, schema-driven LLM extraction.
- `nom.llm.Ollama`, `nom.llm.OpenAI`, `nom.llm.Anthropic` adapters wired up.
- Built-in schemas: `Contract`, `OfficialDoc`, `Receipt`, `IDCard`.

### Planned for v0.2.0
- `nom.prompts.contracts`, `nom.prompts.gov_docs` — versioned prompt library.

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
