# Benchmark datasets

Curated and licensed Vietnamese corpora for evaluating `nom-vn`.

## `diacritic_eval_v0.txt` — diacritic restoration evaluation

- **Size**: 55 sentences across 4 registers (15 contract, 12 official, 15 conversational, 13 news)
- **License**: CC0 (public domain)
- **Source**: Hand-curated by Neural Research Lab, 2026-04-25
- **Use**: input for `benchmarks/accuracy/bench_diacritics.py`

The harness strips diacritics from each sentence, calls `nom.text.fix_diacritics`, and measures word-level accuracy against the original.

## How to add a new dataset

If you'd like to contribute a Vietnamese corpus:

1. Confirm the license allows redistribution (Apache 2.0 / CC-BY / CC0 / public domain).
2. Add it under `benchmarks/data/<dataset_name>/`.
3. Include a `LICENSE` file in the dataset folder citing the origin.
4. Add a `README.md` describing source, size, supported tasks.
5. If the dataset is large (>1MB), consider a `download.sh` that fetches it.

## What we'll integrate next

- **VLSP shared-task data** — pending license review (some VLSP corpora are research-only)
- **Vietnamese Wikipedia samples** — CC-BY-SA, easy to fetch
- **Public OCR test set** — looking for a permissive Vietnamese OCR corpus with ground truth
- **Public contract corpus** — synthetic contracts (we'll generate) since real contracts are private
