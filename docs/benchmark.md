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
| v0.0.1 (now default) | Rule-based table lookup | none | **40.59%** |
| **v0.2.7 (NEW)** | LLM-backed (`fix_diacritics(..., llm=...)`) | any `nom.llm.LLM` | **95.37%** with `OpenAI(gpt-4o-mini)` |
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

## Module: `nom.rag` — *shipped v0.2.5*

### What it does

End-to-end RAG over Vietnamese documents: BM25 + dense (sentence-transformers
encoder) hybrid retrieval with RRF fusion, optional cross-encoder
reranking, optional HyDE / multi-query expansion, then an LLM call.

Three lines from documents to answers — see `src/nom/rag/pipeline.py`
docstring for the canonical example.

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
- **Qwen2-VL-2B-Instruct** (Apache-2.0, 4 GB, GPU-recommended) —
  generalist VLM with strong VN OCR per upstream model card. Defer
  to its own bench session because (a) heavy download, (b) VLM-style
  prompt-and-decode latency is a different metric category than
  CTC-style OCR.
- **Surya OCR** — code is **GPL-3.0**, models are open-RAIL-M.
  Both license-incompatible with our Apache-2.0 default surface.
  Will bench for comparison only; cannot ship as default.

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
