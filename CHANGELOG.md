# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for v0.0.3
- **Diacritic ML backend** — what v0.0.2 deferred. We evaluated PyVi (MIT, but
  crashes on common input — `KeyError: 'dr'` on `"duoc"`) and the HuggingFace
  DistilBERT-Viet model (Apache 2.0, ~90%+ accuracy but ~1GB install weight).
  v0.0.3 will integrate one of:
    - DistilBERT-Viet wrapped behind `[diacritics]` extras
    - A trained-from-scratch lightweight char-level model we ship ourselves
- Add `nom.text.is_diacritic_correct()` to detect misplaced tone marks.
- Expanded eval corpus (~500 sentences) drawn from CC-BY-SA Vietnamese Wikipedia
  samples + ODC-BY mC4 Vietnamese.

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
  agreement with underthesea (CRF) at 135× the throughput**, measured on
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
