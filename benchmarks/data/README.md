# Benchmark datasets

Curated and licensed Vietnamese corpora for evaluating `nom-vn`.

> **Top-level catalogue**: see [`docs/datasets.md`](../../docs/datasets.md) for
> the cross-folder summary, intended uses by module, and reproduction recipes.

## Folders

| Folder | Register / modality | Bytes | License | Status |
|---|---|---|---|---|
| `diacritic_eval_v0.txt` | mixed VN sentences (text) | 8 KB | CC0 | hand-curated, in repo |
| `udhr_vi/` | declarative (text + PDF) | 136 KB | CC-BY-SA 4.0 / public domain | fetched |
| `wikisource_vi/` | classical literary (text) | 28 KB | CC-BY-SA 4.0 (PD content) | fetched |
| `wiki_vi/` | encyclopedia (text) | 1.5 MB | CC-BY-SA 4.0 | fetched |
| `tatoeba_vi/` | conversational (text) | 580 KB | CC-BY 2.0 FR | fetched |
| `synthetic_ocr_vi/` | OCR (PNG images) | 576 KB | CC0 | rendered locally |
| `flores_vi/` | MT benchmark (text) | — | CC-BY-SA 4.0 | gated; manual fetch |

Each folder has its own `LICENSE` and `README.md` with attribution and source
URLs. Re-run all fetchers with:

```bash
python benchmarks/data/_fetch_all.py
python benchmarks/data/synthetic_ocr_vi/render.py
```

## How to add a new dataset

1. Confirm the license allows redistribution (Apache 2.0 / CC-BY / CC0 / public domain).
2. Add it under `benchmarks/data/<dataset_name>/`.
3. Include a `LICENSE` file in the dataset folder citing the origin.
4. Add a `README.md` describing source, size, supported tasks.
5. If the dataset is large (>1MB), consider adding the fetch logic to
   `_fetch_all.py` rather than committing the bytes.
6. Update [`docs/datasets.md`](../../docs/datasets.md) so the catalogue stays
   current.

## What we'd integrate next

- **Wikimedia Commons VN signs** (CC-BY-SA / PD per file) — real-world OCR images for `nom.doc`
- **Internet Archive scanned VN books** (US public domain pre-1928) — large scans, via `download.sh`
- **vbpl.vn legal documents** (PD by VN law) — needs HTML scraping; deferred
- **VLSP shared tasks** — research-only, license review pending
