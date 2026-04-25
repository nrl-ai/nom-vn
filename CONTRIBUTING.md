# Contributing to Nôm

Thanks for your interest. Nôm is open-source infrastructure for Vietnamese AI applications, maintained by [Neural Research Lab](https://nrl.ai). We welcome bug reports, fixes, new test cases, dataset contributions, and discussion.

## Quick start (development)

```bash
git clone https://github.com/nrl-ai/nom
cd nom

# Set up environment
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/

# Lint + type-check
ruff check .
ruff format --check .
mypy src/

# Run benchmarks
python benchmarks/perf/bench_text.py
python benchmarks/accuracy/bench_diacritics.py
```

Install pre-commit so checks run automatically before each commit:

```bash
pre-commit install
```

## Reporting a bug

Open an issue with:

1. What you ran (`pip` version, Python version, OS).
2. The exact input string / file that triggered the bug.
3. Expected behavior vs. observed.
4. A minimal reproduction (≤10 lines of code, please).

If the bug is in OCR / diacritic restoration, **always include a Vietnamese sample**. Generic "OCR is wrong" reports can't be acted on.

## Submitting a pull request

1. Fork → branch from `main` → make your change.
2. Add a test in `tests/` covering the change.
3. If you change runtime behavior, update `CHANGELOG.md` under `[Unreleased]`.
4. Run the full test suite: `pytest tests/`.
5. Run lint + format: `ruff check . && ruff format .`.
6. Run type-check: `mypy src/`.
7. Open a PR with a clear summary; reference any related issue.

CI runs all of the above on every PR. Green CI is required before review.

## Adding to the diacritic restoration table

`nom.text.fix_diacritics` uses a curated vocabulary at `src/nom/text/normalize.py:_RESTORE_TABLE`. To add a new entry:

1. Confirm the word is unambiguous (only one common diacritic-bearing form).
2. Add it in the appropriate section (pronouns, verbs, business words, etc.).
3. Add a test case in `tests/test_normalize.py` exercising the new entry.
4. If the word has multiple diacritic forms (e.g., `ma` → `mà`/`má`/`mã`), **don't add it** — these need the v0.1 LLM-backed path.

## Adding a benchmark

Benchmarks live in `benchmarks/`:

- `benchmarks/perf/` — performance, throughput, latency.
- `benchmarks/accuracy/` — quality on a curated VN corpus.
- `benchmarks/models/` — model comparisons (extraction quality across Qwen, Llama, GPT-4, etc.).

Every benchmark must:

- Be reproducible from a clean clone (one command).
- Have a fixed seed if it uses any randomness.
- Document its data source clearly (cite if external).
- Output JSON results to `benchmarks/results/` so CI can track regressions.

**Numbers to be published anywhere (README, `docs/benchmark.md`, website) must be reproducible from a committed script.** Don't publish estimates.

## Adding a Vietnamese dataset

If you'd like to contribute a Vietnamese corpus for evaluation:

1. Confirm the license allows redistribution (Apache 2.0 / CC-BY / public domain).
2. Add it under `benchmarks/data/<dataset_name>/`.
3. Include a `LICENSE` file in the dataset folder citing the origin.
4. Add a `README.md` describing: source, size, what tasks it supports.
5. If the dataset is large (>1MB), consider a `download.sh` that fetches it instead.

## Code style

- 100-char lines, 4-space indent.
- Type hints on all public functions.
- Docstrings on all public functions, with at least one `>>> ` example.
- Comments only when *why* is non-obvious. Don't narrate *what* the code does.

## Communication

- Issues for bugs and concrete proposals.
- Discussions tab for design questions.
- Email `contact@nrl.ai` for security reports (don't open public issues for vulnerabilities).

## License

By contributing, you agree your contributions are licensed under Apache 2.0.
