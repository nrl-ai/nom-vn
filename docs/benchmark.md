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

| Version | Approach | Dependencies | Measured accuracy |
|---|---|---|---|
| v0.0.1 (now default) | Rule-based table lookup | none | **41.06%** |
| **v0.2.7 cloud** | LLM-backed (`fix_diacritics(..., llm=...)`) | any `nom.llm.LLM` | **95.37%** with `OpenAI(gpt-4o-mini)` |
| **v0.2.7 local** | LLM-backed via Ollama | `nom-vn[llm]` + `ollama pull gemma3:4b` | **87.90%** with `Ollama("gemma3:4b")` |
| **v0.2.7 local-max** | LLM-backed via Ollama | `nom-vn[llm]` + `ollama pull gemma4:e4b` | **93.18%** with `Ollama("gemma4:e4b")` |
| v0.0.2 | Wrap PyVi or DistilBERT model | optional `nom-vn[diacritics]` | deferred — license/format issues |

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

### Diacritic backend / hardware grid — *measured 2026-04-26*

Same Toshiiiii1 T5 weights, three execution paths. All hit the identical
97.81 % word accuracy — export is correct, the only thing that varies is
latency.

| Backend | Hardware | Word acc | Mean ms | p50 ms | Notes |
|---|---|---:|---:|---:|---|
| PyTorch | RTX 3090 (CUDA) | 97.81 % | **152** | 148 | Production target for GPU-equipped users |
| PyTorch | CPU (8 cores) | 97.81 % | 377 | 357 | Acceptable for batch / overnight jobs |
| ONNX Runtime | CPU (8 cores) | 97.81 % | 410 | 394 | Slightly slower than PyTorch CPU |

**ONNX runtime adds no value here.** Modern PyTorch with MKL-DNN is
already optimal for a 200 M T5 in eager mode. ONNX is worth re-visiting
only with **INT8 quantization** (typical 2-3× CPU speedup at some
accuracy cost) — not measured here; left as a follow-up.

We do not ship an ONNX export step in `nom-vn[diacritic-hf]`. Users who
genuinely need ONNX (cross-platform deployment without a Python+PyTorch
stack) can `optimum-cli export onnx ...` themselves; the export is
deterministic.

### Off-the-shelf VN diacritic seq2seq models — *measured 2026-04-26*

Tracking principle: we did not bench public Apache-licensed VN diacritic
models before recommending a 100M-param distillation. The user flagged
this; we re-measured. **One off-the-shelf model beats every option we
tested, including cloud `gpt-4o-mini`.**

Same 55-sentence corpus (CC0). Bench harness:
`benchmarks/accuracy/bench_diacritic_hf.py`. Hardware: RTX 3090.

| Model | License | Disk | Word acc | Mean s/sent | Notes |
|---|---|---:|---:|---:|---|
| **`Toshiiiii1/Vietnamese_diacritics_restoration_5th`** ⭐ | Apache 2.0 | ~1 GB | **97.81%** | **0.152** | T5 200 M, safetensors |
| (cloud `gpt-4o-mini`) | proprietary | — | 95.37% | 1.270 | reference ceiling |
| local `gemma4:e4b` Q4 | Apache 2.0 | 9.6 GB | 93.18% | 1.370 | from LLM grid |
| local `gemma3:4b` Q4 | Apache 2.0 | 3.3 GB | 87.90% | 1.100 | from LLM grid |
| `bmd1905/vietnamese-correction` | Apache 2.0 | ~1.6 GB | 15.57% | 0.301 | Fails — trained for spelling, not diacritic-only |
| `qthuan2604/BARTPho_Syllable_Restore_Diacritics_Vietnamese` | MIT | ~1.6 GB | not benched | — | Self-reported CER 38.85 % is below rule baseline; skipped |
| (rule baseline) | — | 0 | 41.06% | <0.001 | reference floor |

**Toshiiiii1 wins decisively:**

- **+2.44 pp** over cloud `gpt-4o-mini` (97.81 % vs 95.37 %).
- **+9.91 pp** over best local LLM (`gemma3:4b` at 87.90 %).
- **8 × faster** than the cloud LLM (0.152 s vs 1.27 s) and **7 × faster** than local LLMs.
- **Apache 2.0 + safetensors** — fully shippable per CLAUDE.md principle 11.
- **~10 × smaller on disk** than `gemma4:e4b` (1 GB vs 9.6 GB).

**Action:** retract the "distil a 100 M VN diacritic model" recommendation
in `docs/training_plan_2026q2.md` (v0.2.12) — there's nothing to distil
*to* that public Apache models don't already cover. Add as the
recommended production path:

```python
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

restorer = HFDiacriticModel()  # Toshiiiii1 default, lazy-loads on first call
out = fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3", model=restorer)
# → 'Hợp đồng này được lập ngày 14 tháng 3'
```

Install: `pip install "nom-vn[diacritic-hf]"` (pulls `transformers<5` +
`torch` + `sentencepiece`). The transformers cap is required: ≥5.6 has a
slow-T5-tokenizer regression that breaks the Toshiiiii1 model load.

**Why we missed this initially:** the v0.2.7 → v0.2.10 push focused on
LLM-backed diacritic restoration (the prior assumption was "all good VN
diacritic models are pickle-shipping or behind NC licenses"). The
benchmark.md "v0.0.2 backend options under evaluation" table from the
v0.0.1 era still listed Apache candidates as "deferred — license/format
issues" without the actual measurements. The 2026-04-26 audit found one
that meets every constraint.

**Cross-check:** Toshiiiii1's model card reports no metrics, so we have
no upstream number to compare. Our 97.81 % on the small 55-sentence
corpus is near the ceiling — there are only ~12 wrong-restored words
out of 777, and several are register-rare or domain-specific (legal-VN
abbreviations the training data may not cover well). For a sanity check,
on the larger `wikisource_vi` prose we observed similar character-level
accuracy in spot checks; a full multi-corpus bench is the v0.3 follow-up.

Reproduce: `python benchmarks/accuracy/bench_diacritic_hf.py
Toshiiiii1/Vietnamese_diacritics_restoration_5th --json
benchmarks/results/baseline_diacritic_toshiiiii_t5.json`

### Local LLM grid — *measured 2026-04-26*

Goal: identify the smallest **local quantized model** that hits usable VN diacritic accuracy for user-machine deployment. All models served via Ollama 0.21.2 (llama.cpp backend) with `Q4_K_M` quantization (Ollama default), structured output (`format` JSON schema), `think: false`, temperature 0. Hardware: RTX 3090 24GB. Same `diacritic_eval_v0.txt` corpus.

Methodology per CLAUDE.md §12: 3 warmup calls, 55 timed sentences, per-call latency aggregated.

| Model | Q4 size | Word acc | Diacritic recall | Mean s/sent | p95 s/sent |
|---|---:|---:|---:|---:|---:|
| **`gemma4:e4b`** | 9.6 GB | **93.18%** | 92.22% | 1.37 | 1.68 |
| **`gemma3:4b`** ⭐ default | **3.3 GB** | **87.90%** | 87.50% | 1.10 | 1.22 |
| `qwen3:8b` | 5.2 GB | 87.26% | 86.19% | 0.93 | 1.07 |
| `gemma4:e2b` | 7.2 GB | 85.33% | 84.55% | 1.23 | 1.47 |
| `qwen3:4b` | 2.5 GB | 47.36% | 40.48% | 0.94 | 1.06 |
| (rule baseline) | 0 | 41.06% | 34.88% | <0.001 | — |
| `llama3.2:3b` | 2.0 GB | 38.35% | 33.69% | 1.50 | 1.95 |
| `qwen3:1.7b` | 1.4 GB | 18.15% | 6.92% | 0.63 | 0.73 |
| `gemma3:1b` | 0.8 GB | 15.32% | 3.22% | 1.41 | 1.90 |
| `phi4-mini` | 2.5 GB | 6.95% | 2.13% | 2.32 | 10.24 |
| (cloud `gpt-4o-mini`) | — | 95.37% | 94.61% | 1.27 | — |

**Findings:**

1. **Gemma family wins the multilingual fight.** Both `gemma3:4b` and `gemma4:e4b` outperform Qwen3 and Llama at similar size — multilingual training pays off for VN.
2. **3-4B params is the floor for usable VN diacritic.** Sub-2B models (gemma3:1b, qwen3:1.7b) all fall *below* the rule baseline. The quality cliff is sharp.
3. **Gemma 4's "E2B/E4B" naming is about active params, not file size.** The multimodal weights (vision + audio encoders) inflate disk: `e2b` = 7.2 GB Q4, `e4b` = 9.6 GB Q4. For a text-only task like diacritic restoration, this is dead weight on download.
4. **`gemma3:4b` is the best size/quality tradeoff for `nom-vn`.** 3.3 GB fits 4-6 GB VRAM laptops, 87.9% acc within 7.5pp of cloud at 1.1 s/sent. Recommended default for the local LLM path.
5. **Llama 3.2 / phi4-mini disqualified.** Llama tokenizer not balanced for VN; phi4-mini hangs on hard sentences (p95=10s).
6. **Cloud is +2pp over best local.** `gpt-4o-mini` at 95.37% only edges out `gemma4:e4b` (93.18%) by 2.2pp; both are above the practical-usability bar.

**Two engineering fixes shipped to make this measurable** (see [#PR](https://github.com/nrl-ai/nom-vn) and `src/nom/llm/ollama.py` + `src/nom/text/normalize.py`):

- Pass `think: false` to Ollama. Qwen3 thinking-mode emitted CoT to a separate `thinking` field, leaving `content` empty — `qwen3:4b` previously scored 0%.
- Switch `fix_diacritics(llm=...)` to **structured output** via Ollama's `format` JSON schema. Forces `{"restored": "..."}` shape; small models (qwen3:4b, gemma3:4b) can no longer ramble explanations into the response. Quality jumped from <50% to 87-93% across the grid.

Reproduce one model: `python benchmarks/accuracy/bench_diacritics.py --llm ollama --llm-model gemma3:4b --warmup 3`
Reproduce the full grid: `OLLAMA_BASE_URL=http://localhost:11434 ./benchmarks/accuracy/run_diacritic_local_grid.sh`
Aggregate JSONs: `python benchmarks/accuracy/_summarize_diacritic_grid.py`
Per-model JSONs: `benchmarks/results/local_diacritic_grid/diacritics_*.json`

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

### Word segmentation — *measured 2026-04-26*

Two backends, real gold-standard corpus:

- `nom.text.word_tokenize` — pure-Python rule + compound-table merge, zero deps
- `underthesea.word_tokenize` — CRF model, Apache 2.0, opt-in via `nom-vn[nlp]`

Corpus: **UD_Vietnamese-VTB test split** ([UniversalDependencies/UD_Vietnamese-VTB](https://github.com/UniversalDependencies/UD_Vietnamese-VTB), CC-BY-SA-4.0). 800 sentences, 11,692 gold word tokens. Methodology: warmup 3 + best-of-5 throughput; predicted token spans matched against gold spans by exact (start, end) char range.

| Tokenizer | Precision | Recall | **F1** | Throughput | Notes |
|---|---:|---:|---:|---:|---|
| `underthesea==9.4.0` | 95.94% | 95.46% | **95.70%** | 38,102 tok/s | CRFsuite native binary; ~5 MB on disk |
| `nom.text` (rule) | 70.94% | 82.90% | **76.46%** | **747,117 tok/s** | Pure-Python; zero deps; 0 model |

**Findings:**

1. **underthesea is +19.24 pp F1 above `nom.text`** — the CRF training data wins decisively on linguistic compound boundaries (multi-syllable proper names, fixed phrases like *mã số*, *địa chỉ*, *Nguyễn Thị Hương*).
2. **`nom.text` is ~20× faster** (747 k vs 38 k tok/s). For RAG indexing, BM25 tokenization, lightweight cleanup — speed wins; the F1 gap doesn't matter when downstream is a bag-of-words retriever.
3. **`nom.text` recall (82.9 %) > precision (70.9 %)** — it over-splits. The compound table catches some merges (398 hits across the corpus) but is far from CRF coverage.

**Cross-check vs published numbers** (CLAUDE.md §7):

- underthesea reports ~94 % F1 on the VLSP 2013 test set [1]; our 95.70 % on UD-VTB test is ~1.5 pp above that — plausibly because UD-VTB is a slightly easier register (literary prose) than VLSP 2013 (mixed news/business). Same order of magnitude — no methodology divergence to chase.
- We do not separately bench PyVi: it's auto-rejected per CLAUDE.md principle 11 (ships `.pkl` model files = arbitrary code execution on load).

**Recommendation for `nom-vn`:**

| Use case | Pick |
|---|---|
| RAG indexing, BM25, tokenized search | `nom.text` — speed dominates |
| NER / dependency parsing / linguistic analysis | `nom-vn[nlp]` → `underthesea` — F1 dominates |
| OCR post-cleanup, diacritic restoration tokenization | `nom.text` — F1 gap is tolerable; zero deps wins |

The two are complementary, not interchangeable — surface this in the API docs so users don't pick the wrong one and blame the F1 gap.

Reproduce: `python benchmarks/accuracy/bench_segment.py --corpus ud_vtb --split test --json benchmarks/results/baseline_segment_ud_vtb_test.json`
Baseline: `benchmarks/results/baseline_segment_ud_vtb_test.json`

[1]: [Underthesea README](https://github.com/undertheseanlp/underthesea) — reported VLSP 2013 numbers.

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

### The PDF parsing layer underneath — *measured 2026-04-26*

We do **not** ship PyMuPDF. Its AGPL license is incompatible with our Apache-2.0 default. Instead we use **pypdfium2** (BSD-3 wrapper over Google's PDFium, Apache-2.0) as the fast text-extraction default and keep **pdfplumber** for table-rich documents.

Corpus: `benchmarks/data/synthetic_pdf_vi/vn_legal.pdf` — synthetic 7-page Vietnamese PDF built from real public-domain VN prose (UDHR + Wikisource Truyện Kiều prefaces) with a clean Unicode text layer (DejaVuSans embedded). Generator: `benchmarks/data/synthetic_pdf_vi/_generate.py`. Ground truth: 18,877 chars committed alongside.

The shipped `udhr_vi/udhr_vie.pdf` cannot be used here — it embeds a custom font without a ToUnicode CMap, so every extractor (pdfplumber, pypdfium2, PyMuPDF) returns CIDs / garbled bytes. Documented in the bench script.

Methodology: warmup 3 + best-of-5 (CLAUDE.md §12). Char-overlap fidelity uses NFC-normalised multiset intersection against the ground truth.

| Library | License | Best-of-5 (s) | Throughput | Char overlap |
|---|---|---:|---:|---:|
| **`pypdfium2==5.7.1`** ⭐ default | BSD-3 / Apache-2.0 | **0.0079** | **2,350,431 chars/s** | **99.81%** |
| `pdfplumber==0.11.9` | MIT | 0.3654 | 51,052 chars/s | 99.81% |

**Findings:**

1. **`pypdfium2` is 46× faster** than pdfplumber on text-only extraction with **identical fidelity** (99.81% — both miss the same ~36 chars, mostly Han glyphs DejaVuSans can't render).
2. **License is the headline.** PyMuPDF's published 19× speedup on `py-pdf/benchmarks` is real — but its AGPL forces every downstream project to ship as AGPL too. PDFium under pypdfium2 gives us the same order-of-magnitude speedup with no license trap.
3. **pdfplumber stays in `nom-vn[doc]`** — it's still the better choice when a document has tables. The `nom.doc` pipeline picks per-document at parse time.

**Recommendation:**

| Use case | Pick |
|---|---|
| Plain text extraction (RAG, search indexing) | `pypdfium2` — speed wins, license is clean |
| Tables / forms / structured layout | `pdfplumber` — better cell detection |

Reproduce: `python benchmarks/perf/bench_pdf_extract.py`
Baseline: `benchmarks/results/baseline_pdf_extract.json`

Build the corpus from a clean clone: `python benchmarks/data/synthetic_pdf_vi/_generate.py` (requires DejaVuSans — `apt install fonts-dejavu`).

**Note on PyMuPDF / fitz** — we keep them out of dependencies entirely. Users who legitimately need PyMuPDF (e.g. internal AGPL-tolerant projects) can install it themselves and call it directly; we don't expose a wrapper that would muddy the license boundary.

**Docling (IBM, MIT) — measured 2026-04-26.** Same VN PDF, warmup 2 + best-of-3, default `DocumentConverter()`:

| Library | Best (s) | Throughput | Char overlap | Disk |
|---|---:|---:|---:|---:|
| pypdfium2 | **0.0079** | 2,350,431 chars/s | 99.81% | <10 MB |
| pdfplumber | 0.3654 | 51,052 chars/s | 99.81% | <5 MB |
| docling | 1.1889 | 15,703 chars/s | 99.72% | ~1 GB (PyTorch + DocLayNet + TableFormer) |

Docling is **150× slower than pypdfium2** on this Unicode-clean text PDF and slightly *worse* on fidelity (99.72% vs 99.81%) — the ML layout pipeline pays no dividends when the PDF already has a clean text layer. Docling earns its cost on **complex layouts** (multi-column, tables, formulas, mixed text+image) where pdfplumber's heuristics break. Not measured in-house yet on a table-rich VN PDF.

**Recommendation for Docling:** keep it OUT of `nom-vn[doc]` for now. If a user-facing complex-layout corpus emerges (legal forms, government reports), we'll add a `nom-vn[docling]` extra and surface it as `nom.doc.layout_extract()`. Until then, the dependency weight (~1 GB ML stack + safetensors) is unjustified for plain-text PDFs.

Earlier landscape table from [py-pdf/benchmarks](https://github.com/py-pdf/benchmarks) for context (academic + business mixed PDFs):

| Library | Avg time per doc | Notes |
|---|---:|---|
| PyMuPDF (fitz) | 0.5 s | Not shipped — AGPL |
| pypdf | 4.2 s | MIT, basic ops |
| pdfplumber | 9.5 s | Richest table extraction |

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

## Module: `nom.rag` — *shipped v0.2.5*

### What it does

End-to-end RAG over Vietnamese documents: BM25 + dense (sentence-transformers
encoder) hybrid retrieval with RRF fusion, optional cross-encoder
reranking, optional HyDE / multi-query expansion, then an LLM call.

Three lines from documents to answers — see `src/nom/rag/pipeline.py`
docstring for the canonical example.

### Embedder-only retrieval — *measured 2026-04-26*

A direct two-tower comparison: encode every doc + every question, rank docs
by cosine. No BM25, no fusion, no reranker — every quality difference is
purely the embedder. This catches cases where an embedder's STS-tuned
training distribution doesn't transfer to retrieval (the asymmetric Q→Doc
task the RAG pipeline actually does).

Corpus: `benchmarks/rag/fixtures/vn_legal_zalo_5k.json` (5,061 docs / 80
questions, sampled from Zalo AI 2021 Legal QA, MIT). Hardware: RTX 3090.

| Model | License | Disk | R@1 | R@10 | MRR@10 | docs/s |
|---|---|---:|---:|---:|---:|---:|
| **`bkai-foundation-models/vietnamese-bi-encoder`** ⭐ | Apache 2.0 | ~383 MB | **76.25 %** | **98.75 %** | **0.8604** | 60 |
| `dangvantuan/vietnamese-embedding` (current default) | Apache 2.0 | ~440 MB | 35.00 % | 67.50 % | 0.4449 | 53 |

bkai wins by **+41.25 pp R@1 and +31.25 pp R@10** in *smaller* on-disk size and
similar throughput. The gap is structural, not tunable:

- `dangvantuan` was fine-tuned on **STS** (symmetric similarity) — strong
  on benchmarks like VN-STS but the asymmetric question→document
  retrieval task is out of distribution.
- `bkai` was trained with **MultipleNegativesRankingLoss** on Q→Doc pairs
  from MS MARCO + SQuAD v2 + 80 % of Zalo Legal — exactly the task we run.

**Catch:** bkai requires word-segmenter preprocessing
(multi-syllable VN words joined with underscores). The
`nom.embeddings.BKaiEmbedder` class wraps `underthesea` to do this
automatically. Install: `pip install "nom-vn[embeddings,nlp]"`.

**Cross-check:** bkai's published Zalo Legal full-corpus numbers
([model card](https://huggingface.co/bkai-foundation-models/vietnamese-bi-encoder))
report Acc@1 73.28, Acc@10 93.59, MRR 80.73. Our 5k subset (76.25, 98.75,
0.8604) is slightly higher because the subset has fewer distractors —
order of magnitude consistent. No methodology divergence.

**Action for v0.2.x:** add `BKaiEmbedder` as opt-in, do NOT switch the
default in `nom.rag` / `nom.retrieve` — that would invalidate every
existing user's persisted embedding cache. The 0.3.x major release will
flip the default; for now opt-in keeps cache compatibility.

```python
from nom.embeddings import BKaiEmbedder
from nom.rag import RAG
rag = RAG(embedder=BKaiEmbedder(device="cuda"))
```

Reproduce: `python benchmarks/rag/bench_embedder_compare.py
--json benchmarks/results/baseline_embedder_compare_zalo5k.json`

### Vietnamese RAG model grid — *measured 2026-04-25*

Two fixtures, both sampled from
[GreenNode/zalo-ai-legal-text-retrieval-vn](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn)
(MIT). Hardware: NVIDIA RTX 3080 Laptop, fp16, warmup=1, timed=1-2
(best-of-N per CLAUDE.md principle 12).

#### Full corpus — `vn_legal_zalo_full.json` (61,068 articles, 82,696 chunks, 788 questions)

| Retriever | recall@1 | recall@3 | recall@5 | recall@10 | mrr@10 | p50 ms |
|---|---:|---:|---:|---:|---:|---:|
| BM25 | 0.395 | 0.664 | 0.725 | 0.780 | 0.535 | 430 |
| Dense (dangvantuan) | 0.237 | 0.379 | 0.466 | 0.537 | 0.328 | 18 |
| Hybrid (RRF) | 0.368 | 0.602 | 0.690 | 0.783 | 0.505 | 491 |
| **Hybrid + bge-reranker-v2-m3** | **0.572** | **0.802** | **0.846** | **0.868** | **0.688** | 1539 |

#### Subset corpus — `vn_legal_zalo_5k.json` (5,061 articles, 6,833 chunks, 80 questions)

| Embedder | Retriever | recall@1 | recall@3 | recall@10 | mrr@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| `dangvantuan/vietnamese-embedding` (768-d, ~440 MB) | BM25 only | 0.762 | 0.912 | 0.975 | 0.843 | 27 | 48 |
|  | Dense only | 0.412 | 0.725 | 0.863 | 0.585 | 15 | 25 |
|  | Hybrid (RRF) | 0.650 | 0.875 | 0.975 | 0.780 | 59 | 113 |
|  | + `BAAI/bge-reranker-v2-m3` | **0.863** | **1.000** | **1.000** | **0.931** | 681 | 747 |
|  | + `namdp-ptit/ViRanker` | 0.850 | 0.963 | 1.000 | 0.913 | 687 | 743 |
| `AITeamVN/Vietnamese_Embedding` (1024-d, ~2.3 GB, BGE-M3 base) | BM25 only | 0.762 | 0.912 | 0.950 | 0.843 | 24 | 41 |
|  | Dense only | **0.825** | 0.963 | 0.975 | 0.894 | 47 | 77 |
|  | Hybrid (RRF) | 0.800 | 0.963 | 0.975 | 0.884 | 97 | 131 |
|  | + `BAAI/bge-reranker-v2-m3` | **0.863** | 0.988 | 0.988 | 0.923 | 720 | 786 |
|  | + `namdp-ptit/ViRanker` | **0.863** | 0.963 | 0.988 | 0.914 | 718 | 799 |

Reproduce: `bash benchmarks/rag/run_grid.sh`. Per-config baseline JSONs
under `benchmarks/rag/baselines/zalo_5k__*.json` and mirrored to
[nrl-ai/vn-rag-bench](https://huggingface.co/datasets/nrl-ai/vn-rag-bench).

### Findings

1. **Embedder choice matters more than reranker choice — for the
   bi-encoder stage.** Swapping from `dangvantuan` to `AITeamVN` doubles
   dense recall@1 (0.412 → 0.825). The `AITeamVN/Vietnamese_Embedding`
   BGE-M3 finetune was specifically tuned on Zalo Legal QA, which shows
   in the in-domain numbers.
2. **Rerankers converge.** Both `BAAI/bge-reranker-v2-m3` and
   `namdp-ptit/ViRanker` bring final recall@1 to ~0.863 regardless of
   feeder embedder. The reranker dominates the final ranking once the
   gold article is in the top-30 candidate pool.
3. **Best peak quality:** `dangvantuan` + `BAAI/bge-reranker-v2-m3` —
   recall@10 = 1.000 and recall@3 = 1.000 on this fixture. The dangvantuan
   embedder's higher BM25 affinity (its dense leg is weak so RRF leans
   on BM25) lifts recall@10 ceiling.
4. **Skip-the-reranker option:** `AITeamVN` dense alone gets recall@1 =
   0.825 in 47 ms p50 — about **15× faster** than +rerank, with only 4%
   absolute recall@1 lost. Right pick for latency-sensitive deployments
   where 825/863 is acceptable.
5. **BM25 is shockingly competitive** on legal Vietnamese — *at small
   corpus size*. On the 5k subset BM25 hits recall@1 = 0.762, but on
   the full 61k corpus that drops to 0.395. **The corpus-size effect
   dominates** for lexical retrieval; dense / reranker stages get more
   important as the distractor pool grows.
6. **The reranker becomes more critical at scale**, not less. Going
   from hybrid → hybrid+rerank lifts recall@1 by 0.213 absolute on the
   5k subset and 0.204 absolute on the full 61k corpus — proportionally
   a much bigger relative lift on the full corpus (+55% relative vs
   +33% relative).
7. **Pure-Python BM25 was the bottleneck at scale.** On the full 61k
   corpus our v0.2.5 BM25.search() ran at 430ms p50 — far slower than
   dense on GPU (18ms). v0.2.6 swapped to
   [`bm25s`](https://github.com/xhluca/bm25s) (MIT, scipy.sparse): same
   bit-identical recall, **607× faster search** (0.7ms p50). See
   `benchmarks/results/bm25_compare__zalo_full.json` for the full
   table. The dense leg is now the per-query bottleneck.

### Cross-checking against published numbers (per CLAUDE.md rule #7)

- **Multi-stage IR for VN Legal** (PKAW 2022, arXiv:2209.14494):
  reports F2 = 0.741 on the full Zalo corpus with PhoBERT-large +
  sqrt(BM25)·cos hybrid + 3-round hard-negative mining. Our recall@10
  = 0.868 on the full 61k corpus implies a comparable F2 (≈0.6-0.7),
  achieved off-the-shelf with bge-reranker-v2-m3 — no fine-tuning.
  Reasonable alignment.
- **UIT 2024** (arXiv:2507.14619): Vietnamese-bi-encoder + PhoRanker,
  cross-encoder MRR@10 = 79.11% on 261k legal docs. Our MRR@10 = 0.688
  on the full 61k corpus — ~10 points lower; explained by (a) we use
  off-the-shelf bge instead of PhoRanker which is fine-tuned on legal
  data, and (b) corpus-size effects work both ways. Adding PhoRanker
  to our grid is a reasonable next step (excluded so far for the
  VnCoreNLP Java dep).
- **AITeamVN/Vietnamese_Embedding model card**: claims +27.9% Acc@1
  over base BGE-M3 on legal-domain retrieval. Our dense Acc@1 = 0.825
  on 5k subset vs base BGE-M3 (untested by us) — would need to bench
  BGE-M3 on the same fixture to confirm the lift size. **Open: add
  BGE-M3 to the grid** to verify the AITeamVN finetune's published
  advantage.
- **PhoRanker NDCG@10 = 0.7422 on MMARCO-VI** ([model card](https://huggingface.co/itdainb/PhoRanker)):
  not measured — PhoRanker requires VnCoreNLP (Java JVM), excluded
  from this grid intentionally.

### Recommended config (default in `nom-vn` v0.2.5)

```python
from nom.rag import RAG, CrossEncoderReranker
rag = RAG.from_documents(
    docs,
    llm=Ollama(model="qwen3:8b"),
    embedder=VietnameseEmbedder(),                  # 440 MB, dim 768
    reranker=CrossEncoderReranker(),                # bge-reranker-v2-m3
)
answer = rag.ask(question, rerank=True, rerank_candidates=30)
```

For latency-bound deployments without a GPU, drop the reranker and use
`AITeamVNEmbedder()` (better dense, no cross-encoder tax).

---

## Module: `nom.doc.ocr` — *real-baseline measured 2026-04-26*

### What it does

Runs an OCR engine over Vietnamese images (PDF pages, scans, photos)
and returns plain text. v0.2.x ships the Tesseract path; later versions
will add VLM and VN-specialised options as they earn their dependency
weight on the bench.

### Vietnamese OCR engine grid — *measured 2026-04-26*

**Real corpus:** `vn_ocr_subset` — 478 images deterministically sampled
(seed=42) from
[`ducto489/ocr_datasets`](https://huggingface.co/datasets/ducto489/ocr_datasets)
shard 0 (Apache-2.0), filtered to rows containing Vietnamese diacritics
and at least 8 characters of ground-truth text. Mostly machine-rendered
prose at varying noise levels — representative of real document OCR
inputs.

Hardware: CPU (8 cores, no GPU contention with the RAG bench), warmup=1,
timed=2, p50/p95 reported best-of-N.

| Engine | License | CER | WER | diacritic-CER | exact match | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| **Tesseract 5** (`vie` traineddata) | Apache-2.0 | **0.0819** | **0.3771** | **0.1193** | **0.345** | 447 | 656 |
| EasyOCR 1.7 (`vi`) | Apache-2.0 | 0.1176 | 0.5304 | 0.2052 | 0.218 | **183** | **431** |

JSON baselines under `benchmarks/results/ocr_vn_subset__*.json` and
mirrored to
[nrl-ai/vn-rag-bench](https://huggingface.co/datasets/nrl-ai/vn-rag-bench).

### Findings

1. **The synthetic fixture is not a benchmark.** `synthetic_ocr_vi/clean`
   gives Tesseract CER = 0.000 / exact = 1.000 — perfect. `synthetic/noisy`
   gives CER = 0.0064. Both are too easy to rank engines. Real ducto489
   data drops Tesseract to CER = 0.082 — that's the honest baseline.
2. **Diacritic-CER (11.9%) is ~46% worse than overall CER (8.2%)** —
   confirming the Vietnamese-reader-felt failure mode. Tone marks
   (acute, grave, hook, tilde, dot below) are 1–3 pixels and the first
   thing OCR loses on noisy scans. A diacritic-aware reranking or
   post-OCR fix would help here.
3. **Latency is ~450 ms per image on 8 CPU cores.** Tesseract is C++
   under the hood and doesn't parallelise within a page; throughput
   improvements come from running multiple pages in parallel at the
   pipeline level, not from tuning Tesseract internals.
4. **Tesseract beats EasyOCR on every quality metric for VN.** CER
   8.19% vs 11.76%, diacritic-CER 11.93% vs 20.52%, exact-match 34.5%
   vs 21.8%. EasyOCR is 2.4× faster (183 ms vs 447 ms p50) but the
   accuracy gap dominates for document Q&A use cases — losing 13%
   absolute exact-match for 264 ms of latency is a bad trade.
   **Default stays Tesseract.** EasyOCR may be useful for high-throughput
   bulk-indexing use cases where some accuracy can be traded; we
   surface both options in `bench_ocr_real.py`.

### Engines surveyed but not yet measured

- **VietOCR** (Apache-2.0, VN-specialised Transformer) — `pip install
  vietocr` errors on Python 3.13 (`KeyError: '__version__'` in setup.py).
  Pinned for follow-up; the upstream needs a Python-3.13-compatible
  `pyproject.toml`.
- **PaddleOCR PP-OCRv5** (Apache-2.0, lightweight ~150 MB) — most
  promising next candidate. Reported CER ~0.94 on OmniDocBench
  multilingual; not VN-specific but typically beats Tesseract on
  rendered text.
- **Surya OCR** — code is **GPL-3.0**, models are open-RAIL-M.
  Both license-incompatible with our Apache-2.0 default surface.
  Will bench for comparison only; cannot ship as default.

### VLM OCR — *measured 2026-04-26*

Tested whether a general-purpose Vision-Language Model can match
purpose-built OCR on Vietnamese line-image transcription.

**Engine:** `qwen2.5vl:3b` and `qwen2.5vl:7b` (Apache-2.0) via Ollama
0.21.2 on RTX 3090. Q4_K_M quantization. Prompt: tight Vietnamese
"transcribe exactly, no chatter" (see `OllamaVLM` in
`benchmarks/accuracy/bench_ocr_real.py`). Defensive output trim for
think-tags, code-fences, and label echoes.

**Corpus:** First 50 images from `vn_ocr_subset` (sampled from
[ducto489/ocr_datasets](https://huggingface.co/datasets/ducto489/ocr_datasets),
Apache-2.0). Single-line clean printed VN text — same images run on
Tesseract and EasyOCR for direct comparison.

| Engine | Q4 size | CER | WER | Diacritic CER | Exact match | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Tesseract 5 (vie)** | ~30 MB | **5.53%** | 26.78% | 9.71% | **38.0%** | **80.6** | 110.5 |
| EasyOCR (vi) | ~150 MB | 9.39% | 43.86% | 19.84% | 18.0% | 31.1 (GPU) | 68.3 |
| qwen2.5vl:7b | 6.0 GB | 31.07% | 140.04% | 33.38% | 18.0% | 818.0 | 1332.2 |
| qwen2.5vl:3b | 3.2 GB | 39.86% | 175.43% | 41.82% | 15.0% | 1165.5 | 3993.6 |

**Findings:**

1. **VLMs lose decisively on single-line clean OCR.** qwen2.5vl:7b
   has CER 31% vs Tesseract's 5.53% — a 25-point gap. The model
   hallucinates: "1892 - Tạp Chí Vogue..." → "1892 92 92 92 92..." (token
   loop), "XÃ CHIỀNG ƠN" → "CHÍNH XÁC", "churchill và tưởng giới thạch"
   → "Churchill và tướng Eisenhower cùng được trao giải thưởng" (whole
   plausible-but-fabricated sentence).
2. **The right tool stays the right tool.** VLMs are trained on full
   pages; on tight line crops without document context, the language
   prior dominates the visual signal and the model drifts into
   "complete-the-sentence" mode. Tesseract's CTC head is purpose-built
   for left-to-right glyph alignment and doesn't have this failure mode.
3. **Latency: VLM is 10× slower** (818 ms vs 80 ms p50). For a 478-image
   batch this is 6.5 min vs 39 s.
4. **Use case for VLM in OCR is elsewhere.** Multi-field document
   extraction (invoice fields, ID cards, forms with checkboxes), scanned
   handwriting, and "OCR + understand the text" workflows are where
   VLMs earn their cost. We've documented this so users don't reach for
   `qwen2.5vl` expecting it to beat Tesseract on simple line images.

**Recommendation:** **Default OCR stays Tesseract.** VLM OCR is
appropriate when the downstream task is *understanding* the document,
not transcribing it — surface as a separate `nom.doc.vlm_extract()`
path in a future release, not a swap-in OCR backend.

Reproduce: `python benchmarks/accuracy/bench_ocr_real.py --corpus
benchmarks/data/vn_ocr_subset --variant none --engines ollama_vlm
--ollama-model qwen2.5vl:7b --ollama-base-url http://localhost:11434
--limit 50`
Baselines: `benchmarks/results/baseline_ocr_vlm_qwen25vl_7b.json`,
`baseline_ocr_tesseract_50.json`, `baseline_ocr_easyocr_50.json`.

### Recommended config (v0.2.x default)

```python
from nom.doc import Pipeline
# Tesseract is wired into nom.doc.OCR by default; install vie traineddata
# via `apt install tesseract-ocr-vie` (or brew).
pipeline = Pipeline()
text = pipeline.run("scanned.pdf").text
```

The cross-checking-against-published rule (CLAUDE.md #7): published
Tesseract `vie` accuracy on synthetic VN benchmarks varies wildly
(70–97%) by image quality. Our 65.5% exact-match number on real
ducto489 mid-noise images sits in the lower end of that range — which
is the corpus, not the engine. Confirmed by the synthetic-clean run
hitting 100%.

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
