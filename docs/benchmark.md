# Nôm — Component Selection & Benchmarks

This document records the components Nôm depends on, why each was chosen, and benchmark numbers where measured. **Numbers are reproducible — every "measured" claim has a script in `scripts/` you can re-run.**

Last updated: **2026-04-25**.

---

## TL;DR — recommended stack

| Module | Component | Status | Why |
|---|---|---|---|
| `nom.text` | Pure stdlib (`unicodedata`) | **shipped v0.0.1** | 9M ops/s, zero deps, deterministic |
| `nom.doc.ocr` (primary) | **VietOCR** (Transformer, VN-specialized) | planned v0.1 | Diacritic-aware; built on VN corpus |
| `nom.doc.ocr` (fallback) | Tesseract 5 with `vie` traineddata | planned v0.1 | Always available, ~70% accuracy baseline |
| `nom.doc.ocr` (cloud) | PaddleOCR PP-OCRv5 | planned v0.1 | 94.5% on OmniDocBench, modular pipeline |
| `nom.doc.pdf` | **PyMuPDF (fitz)** | planned v0.1 | 19× faster than pdfplumber on real PDFs |
| `nom.llm` (local default) | **Qwen3-8B via Ollama** | planned v0.1 | Apache 2.0, runs on consumer GPU, strong VN |
| `nom.llm` (cloud max) | Qwen3-235B-A22B / GPT-4o / Claude | planned v0.1 | Top-tier when budget allows |
| `nom.llm` (vision+doc) | Qwen2.5-VL-72B-Instruct | planned v0.1 | Best open vision-language for structured doc extraction |

Sources for every claim are listed under each module section.

---

## Module: `nom.text` — *shipped*

### What it does

Pure-Python utilities for Vietnamese text:
- `normalize(s)` — Unicode NFC normalization
- `strip_diacritics(s)` — convert to ASCII (đ → d, é → e, etc.)
- `has_diacritics(s)` — boolean
- `is_vietnamese(s)` — heuristic detection (works on diacritic-stripped text too)
- `fix_diacritics(s)` — restore diacritics on common stripped words

### Tests

22/22 passing (`pytest tests/`).

### Accuracy — measured 2026-04-25

Corpus: `benchmarks/data/diacritic_eval_v0.txt` — 55 hand-curated VN sentences across 4 registers (15 contract, 12 official, 15 conversational, 13 news), CC0 licensed.

| Metric | v0.0.1 baseline |
|---|---:|
| Sentences | 55 |
| Words | 776 |
| Words containing diacritics | 666 |
| **Overall word accuracy** | **40.59%** |
| **Overall diacritic recall** | **34.08%** |

By register:

| Register | Word accuracy | Diacritic recall |
|---|---:|---:|
| contracts / business | 50.00% | 44.32% |
| official docs | 39.33% | 29.33% |
| conversational | 44.15% | 39.37% |
| news / long-form | 29.13% | 23.33% |

This is the **honest v0.0.1 baseline** with the current ~120-entry curated vocabulary table. The rule-based path is a zero-dependency stopgap. The roadmap replaces it, not extends it:

| Version | Approach | Dependencies | Expected accuracy |
|---|---|---|---|
| v0.0.1 (now) | Rule-based table lookup | none | **41% measured** |
| v0.0.2 | Wrap PyVi or DistilBERT model | optional `nom-vn[diacritics]` | 90%+ (cited from upstream) |
| v0.1 | LLM-backed via `nom.llm` | user-supplied LLM | best quality |

### v0.0.2 backend options under evaluation

| Option | Source | Approach | Reported accuracy | License |
|---|---|---|---|---|
| **PyVi `ViUtils.add_accents()`** | [trungtv/pyvi](https://github.com/trungtv/pyvi) | trained model wrapper | mature, ~80%+ | MIT |
| **DistilBERT-Viet-Diacritic** | [HF: saeliddp/...](https://huggingface.co/saeliddp/distilbert-viet-diacritic-restoration) | DistilBERT token classification | ~90%+ | Apache 2.0 |
| **restore_vietnamese_diacritics** | [duongntbk](https://github.com/duongntbk/restore_vietnamese_diacritics) | Transformer seq2seq | **94.05%** | MIT |
| **vietai/aivivn-vn-diacritic** | [vietai](https://github.com/vietai/aivivn-vn-diacritic) | Transformer seq2seq | — | Apache 2.0 |

Pick will be based on: dependency weight, CPU-only inference speed, license compatibility, and our own measurement against `diacritic_eval_v0.txt`. We do not publish projected numbers — the v0.0.2 release post will include the measured number on the same corpus.

Reproduce: `python benchmarks/accuracy/bench_diacritics.py`
Baseline tracked at: `benchmarks/results/baseline_v0.0.1.json`

### Performance — measured 2026-04-25 on Python 3.13.9

Corpus: 1,000 contract-style Vietnamese sentences (67,600 chars).

| Function | Latency (best of 3) | Throughput (ops/s) | Throughput (chars/s) |
|---|---:|---:|---:|
| `normalize` | **0.11 ms** | 9,066,758 | 612,912,817 |
| `has_diacritics` | 0.19 ms | 5,325,466 | 360,001,468 |
| `is_vietnamese` | 0.24 ms | 4,254,631 | 287,613,073 |
| `strip_diacritics` | 5.87 ms | 170,368 | 11,516,906 |
| `fix_diacritics` | 5.12 ms | 195,122 | 13,190,280 |
| **Reference: stdlib `unicodedata.normalize` NFC** | 0.12 ms | 8,365,051 | 565,477,425 |
| **Reference: stdlib `unicodedata.normalize` NFD** | 0.48 ms | 2,062,749 | 139,441,817 |

Reproduce: `python benchmarks/perf/bench_text.py`

### Component choice rationale

**Why pure stdlib (no third-party deps):**
- `unicodedata` is in CPython core, zero install friction.
- Performance is sufficient (>500 MB/s on `normalize`).
- Deterministic — no model loading, no network.
- v0.1 may add an LLM-backed `fix_diacritics(..., llm=...)` for ambiguous cases, but the pure-rule path stays.

**Why not `pyvi` or `underthesea` for v0?**
- Both are excellent for tokenization/POS-tagging — out of scope for v0.0.1.
- They'll appear as optional deps in `nom.text.tokenize` (v0.2+) for users who want them.

---

## Module: `nom.doc.ocr` — *planned v0.1*

OCR is the highest-leverage and most-failed-at primitive in Vietnamese AI. We ship three backends with the same interface; default switches by available hardware.

### Backend comparison (research, not in-house tests yet)

| Engine | Accuracy on VN | Speed | Diacritic handling | Setup cost | License |
|---|---|---|---|---|---|
| **Tesseract 5 + `vie`** | ~70-97% (varies wildly with image quality) [1] | 9.8 FPS [2] | **Weak** — confuses stacked diacritics (acute vs hook above on ô) [3] | apt install | Apache 2.0 |
| **EasyOCR** | ~79% general (no VN-specific number found) | 56 FPS [2] | Better than Tesseract on noisy backgrounds [4] | pip install + ~150MB model | Apache 2.0 |
| **PaddleOCR PP-OCRv5** | ~94.5% on OmniDocBench [5] | Slower than EasyOCR [2] | Strong (multilingual training) | pip install + model download | Apache 2.0 |
| **VietOCR (Transformer)** | Trained specifically on VN [6] | Slower (Transformer cost) | **Strongest** — VN-specialized | pip install + custom model | Apache 2.0 |
| **GPT-4o / Claude vision** | ~Best-in-class | API latency | Best in handling stacked tones | API cost | Commercial |

### Recommendation for `nom.doc`

**Default backend: VietOCR (Transformer)** when available, fall back to **Tesseract** for portability.

```python
# Planned v0.1 API
from nom.doc import extract
from nom.doc.ocr import VietOCR, Tesseract, PaddleOCR

# Auto: VietOCR if installed → PaddleOCR → Tesseract
result = extract("scan.pdf", schema={...})

# Explicit
result = extract("scan.pdf", schema={...}, ocr=PaddleOCR())
```

### The PDF parsing layer underneath

For native (non-scanned) PDFs we use **PyMuPDF (fitz)** as the default text/layout extractor.

**Source: [py-pdf/benchmarks](https://github.com/py-pdf/benchmarks)** — measured on a corpus of academic + business PDFs:

| Library | Avg time per doc | Notes |
|---|---:|---|
| **PyMuPDF (fitz)** | **0.5 s** | Fastest, AGPL or commercial license |
| pypdf | 4.2 s | MIT, basic ops |
| pdfplumber | 9.5 s | Richest table extraction, slow |

Trade-off: PyMuPDF's AGPL license is restrictive. We'll expose pdfplumber as a fallback option for AGPL-incompatible projects, accepting the 19× slowdown.

### Sources
- [1] [VietOCR / Tesseract VN test results](https://vietocr.sourceforge.net/)
- [2] [PaddleOCR vs EasyOCR vs Tesseract benchmark — TildAlice](https://tildalice.io/ocr-tesseract-easyocr-paddleocr-benchmark/)
- [3] [Tesseract Vietnamese stack-diacritic issue](https://github.com/tesseract-ocr/langdata/issues/66)
- [4] [Tesseract vs EasyOCR comparison](https://ttsforfree.com/en/blogs/image-to-text-python-tesseract-vs-easyocr/)
- [5] [PaddleOCR PP-OCRv5 release notes](https://www.tenorshare.com/ocr/paddleocr.html)
- [6] [VietOCR (Transformer) — pbcquoc](https://github.com/pbcquoc/vietocr)
- [7] [Survey on Vietnamese Document Analysis (arXiv 2506.05061)](https://arxiv.org/abs/2506.05061)

---

## Module: `nom.llm` — *planned v0.1*

Nôm doesn't bundle a model. We ship adapter classes; users pick which model to point at.

### Recommended models — three brackets

#### Bracket 1 — local, free, runs on a consumer laptop

**Primary: `Qwen3-8B` via Ollama**

- Apache 2.0 license — commercial use OK
- Runs in ~6GB VRAM (Q4 quant) or 16GB RAM CPU
- Strong VMLU performance for its size
- Multilingual including Vietnamese
- One-line install: `ollama pull qwen3:8b`

**Alternative: `Llama-3.1-8B-Instruct`**
- Meta license (commercial OK with conditions)
- Slightly worse VN performance than Qwen3 in 2026 reviews [1]

**Alternative: `Vistral-7B-Chat`**
- Vietnamese-fine-tuned
- License is research-only (per VinAI) — *not for commercial use*

#### Bracket 2 — cloud, mid cost, top open quality

**`Qwen3-235B-A22B`** via Together AI / Fireworks / Alibaba Cloud
- Apache 2.0
- 235B MoE (22B active) — strong Vietnamese
- Top recommendation in 2026 best-VN-LLM guides [1]
- ~$0.50–1/M input tokens via providers

#### Bracket 3 — closed, max quality

| Provider | Model | Why use it |
|---|---|---|
| OpenAI | `gpt-4o` | Best general VN reasoning, vision-capable |
| Anthropic | `claude-sonnet` | Strong long-document reasoning, large context |
| Google | `gemini-2.5-pro` | Cheapest at top tier in 2026 |

### Vision-capable models for `nom.doc` (scanned docs)

For OCR-grade work directly on images (skipping the OCR step entirely):

| Model | License | Notes |
|---|---|---|
| **Qwen2.5-VL-72B-Instruct** | Apache 2.0 | Top open vision-LLM for structured doc extraction [2] |
| GLM-4.5V | open weights | Strong on charts, tables, complex layouts [2] |
| DeepSeek-VL2 | open weights | Good on Vietnamese scanned docs anecdotally |
| GPT-4o (vision) | closed | Best when latency/cost are not constraints |

**Recommendation**: `nom.doc.extract` uses two paths:
1. Native PDF → text → text-only LLM (cheapest, fastest)
2. Scan/image → vision-LLM directly (skips OCR, often higher quality)

### Sources
- [1] [Best Open Source LLM for Vietnamese in 2026 — SiliconFlow](https://www.siliconflow.com/articles/en/best-open-source-LLM-for-Vietnamese)
- [2] [Best LLM for Document Screening in 2026 — SiliconFlow](https://www.siliconflow.com/articles/en/best-open-source-LLM-for-Document-screening)
- [3] [Document Data Extraction in 2026: LLMs vs OCRs — Vellum](https://www.vellum.ai/blog/document-data-extraction-llms-vs-ocrs)
- [4] [VMLU Leaderboard](https://vmlu.ai/leaderboard) — current rankings of VN LLMs
- [5] [Qwen2.5 release notes](https://qwenlm.github.io/blog/qwen2.5-llm/)

---

## Module: `nom.prompts` — *planned v0.2*

Curated, versioned system prompts for VN business documents. **No benchmarks yet — this module's value is in *which prompts win*, not raw speed.**

### Domains we'll cover

| Domain | Why prioritized | Test set source |
|---|---|---|
| **Hợp đồng** (contracts) | Highest-frequency VN business doc | NRL-curated contract corpus |
| **Công văn** (official docs) | Government/SMB workflow staple | VLSP corpora (where licenses allow) |
| **Đơn từ** (applications/petitions) | High volume, low-quality OCR input | Synthetic + community submissions |
| **Email công sở** (business email) | Tone-aware drafting (kính gửi vs cho) | Internal eval set |
| **Hoá đơn / biên lai** (invoices/receipts) | Accounting use-case | Open OCR datasets |

### Versioning

Prompts are versioned (`nom.prompts.contracts.v1`). Once published, never silently changed. Pinning a version is part of the user's reproducibility contract.

---

## Module-level benchmarks NRL contributes (VN-Bench v1)

This is the work that will populate `nrl.ai/bench` with NRL-original numbers (vs. the current page that aggregates VMLU). See [VN-Bench v1 roadmap](../www.nrl.ai/app/[locale]/bench/page.tsx) for the canonical task list.

| Task | Description | Eval | Status |
|---|---|---|---|
| **Contract extraction** | PDF → typed schema | F1 on field accuracy | in development |
| **Official-doc parsing** | Số / ngày / đơn vị / nội dung | Exact match | in development |
| **Scan OCR → JSON** | Image → structured | Char-edit + field accuracy | in development |
| **Tone-mark preservation** | Generation w/ correct diacritics | Diacritic accuracy on long passages | in development |
| **EN/VN code-switching** | Mixed dialogue understanding | Pairwise judge | in development |
| **Legal QA** | Article prediction, citation | Borrowed from VLegal-Bench | partner |

---

## Reproducibility

Every "measured" number in this document is reproducible:

```bash
# Clone
git clone https://github.com/nrl-ai/nom-vn
cd nom-vn

# Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests (currently 22/22 passing)
pytest tests/

# nom.text perf benchmark (table above)
python scripts/bench_text.py
```

Numbers from external sources (OCR engines, LLM leaderboards) are linked back to their canonical posting. Internal claims labeled "measured" carry a corresponding script in `scripts/`.
