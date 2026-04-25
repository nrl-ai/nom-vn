# Benchmarks

Three categories. All reproducible from a clean clone.

```
benchmarks/
├── perf/            performance — throughput, latency
├── accuracy/        quality on a curated VN corpus
├── models/          model comparisons (v0.1+)
├── data/            shared eval corpora (CC0 / CC-BY where noted)
└── results/         baseline JSON snapshots (committed) + ad-hoc runs (gitignored)
```

## Run everything

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python benchmarks/perf/bench_text.py
python benchmarks/accuracy/bench_diacritics.py
python benchmarks/accuracy/bench_ocr.py        # v0.1+ smoke test today
python benchmarks/accuracy/bench_pipeline.py   # v0.1+ smoke test today
python benchmarks/models/bench_extraction.py   # v0.1+ smoke test today
```

## Performance · `perf/bench_text.py`

Measures throughput of every `nom.text` function on a 1,000-sentence Vietnamese contract corpus.

**v0.0.1 baseline** (Python 3.13, single core):

| Function | Throughput |
|---|---:|
| `normalize` | 9.07M ops/s · 613 MB/s |
| `has_diacritics` | 5.33M ops/s |
| `is_vietnamese` | 4.25M ops/s |
| `strip_diacritics` | 170K ops/s |
| `fix_diacritics` | 195K ops/s |

Re-run to reproduce.

## Accuracy · `accuracy/bench_diacritics.py`

Loads the 55-sentence `data/diacritic_eval_v0.txt` corpus, strips diacritics, calls `fix_diacritics`, scores word-level recovery.

**v0.0.1 baseline** (committed at `results/baseline_v0.0.1.json`):

| Metric | Value |
|---|---:|
| Sentences | 55 |
| Words | 776 |
| **Overall word accuracy** | **40.59%** |
| **Overall diacritic recall** | **34.08%** |

Per-register breakdown:

| Register | Accuracy | Diacritic recall |
|---|---:|---:|
| contracts / business | 50.00% | 44.32% |
| official documents | 39.33% | 29.33% |
| everyday / conversational | 44.15% | 39.37% |
| news / long-form | 29.13% | 23.33% |

This is the *baseline* from a small (~120-entry) curated vocabulary. v0.0.2 expands the table to ~1,000 entries; v0.1 adds an LLM-backed restoration path that should beat 90%+. **No projected numbers — we publish them after we measure them.**

```bash
python benchmarks/accuracy/bench_diacritics.py                              # human-readable
python benchmarks/accuracy/bench_diacritics.py --json results/run.json      # machine-readable
```

## Model comparison · `models/bench_extraction.py`

**Status: scaffold for v0.1.** Compares LLMs on Vietnamese document extraction (contracts, official docs, ID cards, receipts).

Today the script is a smoke test that lists the planned models and confirms the harness shape. The real corpus + extractions arrive with v0.1.

Planned model coverage (selection rationale in [BENCHMARK.md](../BENCHMARK.md)):

| Model | Tier | License | Why |
|---|---|---|---|
| qwen3:8b | local | Apache 2.0 | Recommended local default |
| qwen3:235b-a22b | cloud | Apache 2.0 | Top open VN performance |
| llama3.1:8b-instruct | local | Meta | Cost-effective baseline |
| vistral:7b | local | Research-only | VN-fine-tuned reference |
| gpt-4o | cloud | Closed | Best general VN reasoning |
| claude-sonnet | cloud | Closed | Long-doc reasoning |

## Adding to the eval corpora

See [`data/README.md`](data/README.md). Permissive licenses only (Apache 2.0, CC-BY, CC0, public domain).

## Reproducibility contract

- Every published number has a script committed in this directory.
- Baselines live at `results/baseline_<version>.json` (tracked in git).
- Ad-hoc runs (`results/run.json`, etc.) are gitignored.
- No projection, no estimation, no placeholder data in published metrics. Empty is honest; fake is not.
