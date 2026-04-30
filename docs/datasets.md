# Vietnamese benchmark datasets

Catalogue of every Vietnamese corpus shipped with `nom-vn` for testing and
benchmarking. All datasets are license-clean for **redistribution + modification**
(Apache 2.0 / CC-BY / CC-BY-SA / CC0 / public domain). Each folder has its
own `LICENSE` and per-file attribution.

> **Looking for OCR _training_ data?** That's a separate audit:
> [`research/ocr_training_data_vn_2026q2.md`](research/ocr_training_data_vn_2026q2.md)
> covers what's redistributable vs research-only vs commercial, with cost
> estimates for synthetic generation, labeling, and PaddleOCR fine-tuning.

## Quick map

| Dataset | Modality | Register | Size | License | Path |
|---|---|---|---|---|---|
| `diacritic_eval_v0` | text (sentences) | mixed (4 registers) | 55 sentences | CC0 | [`benchmarks/data/diacritic_eval_v0.txt`](../benchmarks/data/diacritic_eval_v0.txt) |
| `udhr_vi` (text) | text (declarative) | formal/translated | ~19 KB | CC-BY-SA 4.0 | [`benchmarks/data/udhr_vi/udhr_vi.txt`](../benchmarks/data/udhr_vi/) |
| `udhr_vi` (PDF) | PDF (text-layer) | formal | ~113 KB | public domain | [`benchmarks/data/udhr_vi/udhr_vie.pdf`](../benchmarks/data/udhr_vi/) |
| `wikisource_vi` | text (prose) | classical literary | ~14 KB across 3 files | CC-BY-SA 4.0 (PD content) | [`benchmarks/data/wikisource_vi/`](../benchmarks/data/wikisource_vi/) |
| `wiki_vi` | text (articles) | encyclopedia | 28 articles, ~1.16M chars | CC-BY-SA 4.0 | [`benchmarks/data/wiki_vi/articles.jsonl`](../benchmarks/data/wiki_vi/) |
| `tatoeba_vi` | text (sentences) | conversational | 31,292 / 3,000 sample / 300 diacritic | CC-BY 2.0 FR | [`benchmarks/data/tatoeba_vi/`](../benchmarks/data/tatoeba_vi/) |
| `udhr_vi` (diacritic 72) | text (sentences) | formal/legal-prose | 72 sentences | public domain | [`benchmarks/data/udhr_vi/diacritic_eval_udhr.txt`](../benchmarks/data/udhr_vi/) |
| `synthetic_ocr_vi` | PNG images | OCR target | 40 images (clean+noisy) | CC0 | [`benchmarks/data/synthetic_ocr_vi/`](../benchmarks/data/synthetic_ocr_vi/) |
| `flores_vi` | text (parallel) | news / mixed | gated, not committed | CC-BY-SA 4.0 | [`benchmarks/data/flores_vi/`](../benchmarks/data/flores_vi/) |
| `ud_vi_vtb` | CoNLL-U (gold word-segmented) | literary | 800 test / 1,123 dev / 1,400 train sentences; 11,692 test gold tokens | CC-BY-SA-4.0 | [`benchmarks/data/ud_vi_vtb/`](../benchmarks/data/ud_vi_vtb/) |

Total committed footprint: **~2.8 MB**.

## What each dataset is good for

| Module | Recommended datasets | Why |
|---|---|---|
| `nom.text` (normalize, fix_diacritics) | `diacritic_eval_v0`, `udhr_vi/diacritic_eval_udhr.txt`, `tatoeba_vi/diacritic_eval_300.txt`, `ud_vi_vtb/test.conllu` | 4-register matrix (formal / business / conversational / literary) |
| `nom.text.word_tokenize` | `ud_vi_vtb` (test split) | Gold word-segmentation P/R/F1 vs underthesea |
| `nom.chunking` | `wiki_vi`, `wikisource_vi`, `udhr_vi` | Long-form prose with paragraph structure |
| `nom.embeddings` | `tatoeba_vi`, `flores_vi` (when available) | Sentence-level evaluation pairs |
| `nom.retrieve` (BM25, dense, hybrid) | `wiki_vi` corpus + handcrafted queries | Diverse encyclopedia topics for IR |
| `nom.rag` | `wiki_vi` (corpus) + `tatoeba_vi` (queries) | End-to-end retrieval + generation |
| `nom.doc` (PDF text extraction) | `udhr_vi/udhr_vie.pdf` | Born-digital PDF baseline |
| `nom.doc` (OCR on images) | `synthetic_ocr_vi` (clean + noisy) | Perfect ground truth, regression-safe |

## Published on Hugging Face Hub

Two datasets we collated for diacritic restoration are mirrored on HF Hub
for easy `datasets.load_dataset` use without cloning the repo:

| HF dataset | License | Splits / configs | What's in it |
|---|---|---|---|
| [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) | CC-BY-SA-4.0 (most restrictive of constituents) | `business_55`, `formal_72`, `conversational_300`, `literary_800` | The 4-register evaluation grid (1,227 sentence pairs) used to bench every diacritic model in this repo. Per-config license noted in the card. |
| [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) | CC-BY-SA-4.0 (per-config: wiki=CC-BY-SA-4.0, news=CC-BY-4.0) | `wiki_500k`, `news_150k` | 500K Wikipedia + 150K NFC-fixed VN news training pairs. Eval-leak guarded against `vn-diacritic-eval`. NFC-normalized at write time. |

Loading:

```python
from datasets import load_dataset

# Eval set — bench any model against the same grid
ds = load_dataset("nrl-ai/vn-diacritic-eval", "business_55", split="train")

# Training pairs — pre-built Wikipedia + news mix
wiki = load_dataset("nrl-ai/vn-diacritic-train", "wiki_500k", split="train")
news = load_dataset("nrl-ai/vn-diacritic-train", "news_150k", split="train")
```

The local copies under `benchmarks/data/` and `training/diacritic/data/`
are bit-identical with the HF versions; either entry point works.

## Reproducing the corpora from a clean clone

```bash
# Text + PDF — all idempotent
python benchmarks/data/_fetch_all.py

# Diacritic eval slices (300 conversational, 72 formal/legal)
python benchmarks/data/tatoeba_vi/build_diacritic_eval.py
python benchmarks/data/udhr_vi/build_diacritic_eval.py

# Synthetic OCR images — deterministic via seeded RNG
python benchmarks/data/synthetic_ocr_vi/render.py
```

The fetcher uses only stdlib (`urllib.request`) plus `huggingface_hub` for
gated-dataset paths. The renderer requires `Pillow` and Vietnamese-capable
system fonts (DejaVu / Lato / FreeFont — present on most Linux distros).

## License posture (our no-pickle + verified-benchmarks policy)

- **Per-folder LICENSE** with explicit attribution rules — never relying on
  global "license file" inheritance.
- **No pickle, no opaque binary** in any committed dataset. PNGs and PDFs are
  open formats; everything else is plaintext or TSV.
- **Reproducible from script** — every committed dataset is regeneratable from
  `_fetch_all.py` or `render.py`. No black-box artifacts.
- **CC-BY-SA "share-alike" caveat**: derivative works that incorporate
  CC-BY-SA datasets inherit the share-alike obligation. The library code itself
  (Apache 2.0) does not — only outputs that bake-in CC-BY-SA *content*.

## Sources we considered and rejected

| Source | Why excluded |
|---|---|
| VLSP shared-task corpora | Research-only license, no redistribution |
| VnExpress / Tuoi Tre / news scrapes | Copyrighted, no permissive license |
| CC-100 / mC4 / CulturaX | License unclear (Common Crawl ToS murkiness) |
| VietAI medical-QA | Research-only |
| Vinacademy / VinAI scanned docs | License unclear |

## Pending additions

- **Wikimedia Commons VN signs** — real-world OCR images, CC-BY-SA / PD per file
- **Internet Archive scanned VN books** — pre-1928 US PD, fetch via `download.sh`
- **vbpl.vn legal documents** — PD by Vietnamese law (Luật SHTT 2005, Art. 15)
