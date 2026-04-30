# Nôm 喃

**Open-source Python toolkit for building Vietnamese AI applications.**

> Named after *chữ Nôm* — the script Vietnam wrote in for a millennium.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/nrl-ai/nom-vn/blob/main/LICENSE)
[![Status](https://img.shields.io/badge/status-v0.2.27-orange)](https://github.com/nrl-ai/nom-vn/blob/main/CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-354%20passing-brightgreen)](https://github.com/nrl-ai/nom-vn/tree/main/tests)

A local-first toolkit. **No data leaves your machine.** Use any LLM (Ollama by default), any embedder, any document type — Nôm wires them into a Vietnamese-aware RAG pipeline you can ship as either a Python library or a deployable chat web app.

**Every default is benched on real Vietnamese data.** Where a public Apache/MIT model beats a multilingual one, we use it. See [docs/benchmark.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/benchmark.md) for the receipts.

---

## The 3-line demo

```bash
pip install "nom-vn[chat]"     # FastAPI + React UI + parsers + embeddings
nom serve                       # opens http://localhost:8080
# upload PDFs/Word/Excel/PowerPoint/images, ask questions in Vietnamese
```

![Nôm — chat with citations grounded in indexed Vietnamese documents](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/02-chat-with-answer.png)

The web app is built into the wheel — there's nothing else to install.

---

## Recommended stack — *measured 2026-04-30*

Every recommendation has a measured number from a script in
[`benchmarks/`](https://github.com/nrl-ai/nom-vn/tree/main/benchmarks) that runs on a clean clone. No projected
numbers. No "based on the model card." Numbers came out of our hardware,
on real Vietnamese corpora, this week.

| Task | Pick | License | Disk | Measured | Beats |
|---|---|---|---:|---|---|
| **Diacritic restoration (default)** [→](https://github.com/nrl-ai/nom-vn/blob/main/docs/tasks/diacritic-restoration.md) | `Toshiiiii1/Vietnamese_diacritics_restoration_5th` (T5 200 M, opt-in) | Apache 2.0 | 1 GB | **97.81 %** word acc on business · 89.40 % literary · 98.14 % formal · 93.94 % conversational | beats cloud `gpt-4o-mini` 95.37 % on business; SOTA on the 4-register matrix |
| **Diacritic restoration (register-balanced)** [→](https://github.com/nrl-ai/nom-vn/blob/main/docs/tasks/diacritic-restoration.md) | [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base) (ViT5 220 M, ours) | Apache 2.0 | 900 MB | 99.43 % formal (+1.29 pp) · 94.12 % conversational (+0.18 pp) · 94.98 % business (-2.83) · 90.24 % literary | wins formal + conversational; pick this for legal docs / chat data, Toshiiiii1 for business-tilted text |
| **Diacritic restoration (fast tier)** [→](https://github.com/nrl-ai/nom-vn/blob/main/docs/tasks/diacritic-restoration.md) | [`nrl-ai/vn-diacritic-small`](https://huggingface.co/nrl-ai/vn-diacritic-small) (BARTpho-syllable 115 M, ours) | Apache 2.0 | 530 MB | 94.44 % business · 86.33 % literary · 90.68 % conv · 91.51 % formal · ~50-100 ms/sent (2.2x faster) | half the params of the base; pick when latency matters more than absolute quality |
| **Diacritic (zero-dep fallback)** | rule-based table (`nom.text.fix_diacritics`) | Apache 2.0 | 0 | 41.06 % word acc · <1 ms | — |
| **Diacritic (local LLM)** | `gemma3:4b` Q4 via Ollama | Apache 2.0 | 3.3 GB | 87.90 % word acc · 1.10 s | `qwen3:8b` (87.26 %), `gemma4:e4b` is +5pp better but 3× larger |
| **Word segmentation (speed)** | `nom.text.word_tokenize` (rule, zero deps) | Apache 2.0 | 0 | F1 76.46 % · 747 k tok/s | — |
| **Word segmentation (quality)** | `underthesea` 9.4.0 (CRF, opt-in) | Apache 2.0 | <10 MB | F1 95.70 % · 38 k tok/s | matches its own published VLSP 2013 numbers |
| **OCR (printed clean lines)** | Tesseract 5 + `vie` traineddata | Apache 2.0 | ~30 MB | CER 5.53 % · 80 ms p50 | EasyOCR (9.39 %), `qwen2.5vl:7b` (31.07 %) |
| **PDF text extraction** | `pypdfium2` (BSD-3 wrap of PDFium Apache-2.0) | BSD-3 / Apache | <10 MB | 99.81 % char overlap · 2.35 M chars/s | `pdfplumber` (51 k chars/s), Docling (15 k chars/s) |
| **Dense embedder (RAG retrieval)** | `bkai-foundation-models/vietnamese-bi-encoder` (opt-in) | Apache 2.0 | 383 MB | R@1 76.25 % · R@10 98.75 % on Zalo Legal QA 5 k | `dangvantuan/vietnamese-embedding` (35.00 % R@1) by +41.25 pp |
| **Dense embedder (default, cache-stable)** | `dangvantuan/vietnamese-embedding` | Apache 2.0 | 440 MB | R@1 35.00 % on Zalo Legal QA 5 k | — |
| **Reranker** | `BAAI/bge-reranker-v2-m3` | Apache 2.0 | ~2 GB | R@1 86.3 % paired w/ dense (Zalo Legal 5 k) | `namdp-ptit/ViRanker` (85.0 %) |
| **BM25** | `bm25s` (Lucene-formula) | MIT | <10 MB | R@1 76.2 % on Zalo Legal 5 k · 0.7 ms/query | 607× faster than v0.2.5 pure-Python implementation |

**The decision in plain English:**

- *Want VN diacritics fixed?* Install `nom-vn[diacritic-hf]` and use the Toshiiiii1 T5. It beats cloud GPT-4o-mini.
- *Want local RAG over Vietnamese documents?* Install `nom-vn[chat,embeddings,nlp]`, swap the default embedder to `BKaiEmbedder`. +41 pp R@1.
- *Need OCR on Vietnamese scans?* Tesseract `vie` is the right call. Don't reach for VLM OCR — VLMs hallucinate on tight line crops.
- *Need PDF text extraction in a license-clean way?* Use `pypdfium2` (we ship it). Skip PyMuPDF — its AGPL forces every downstream into AGPL.

## What ships today

| Module | What it does | Status |
|---|---|---|
| `nom.text` | NFC normalize, rule diacritic restoration, word tokenization. Also: `HFDiacriticModel` (Toshiiiii1 T5, 97.81 %, opt-in) | ✅ |
| `nom.chunking` | VN-aware document chunking | ✅ |
| `nom.embeddings` | `Embedder` Protocol + `VietnameseEmbedder` (default) + `BKaiEmbedder` (recommended, retrieval-trained) + `AITeamVNEmbedder` (BGE-M3 ft) | ✅ |
| `nom.retrieve` | `BM25Retriever` (bm25s, 607× faster than v0.2.5), `DenseRetriever`, hybrid RRF fusion | ✅ |
| `nom.doc` | PDF (`pypdfium2` 46× faster than pdfplumber) / DOCX / XLSX / PPTX / HTML / image (Tesseract OCR) → text | ✅ |
| `nom.llm` | `LLM` Protocol + `Ollama` adapter (default `think=False`) + `OpenAI` + `Anthropic` | ✅ |
| `nom.rag` | One-line RAG composition + cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) | ✅ |
| `nom.chat` | FastAPI server + React/ShadCN UI, `MemoryStore` + `SqliteStore` + pluggable `EmbeddingsCache` | ✅ |

---

## NotebookLM-style document Q&A web app

Three-pane editorial layout: spaces sidebar / chat thread / sources + studio. Dark editorial palette, sharp corners, citation traceability.

Three-pane editorial layout (1920×1080 desktop):

![Default chat view — space selected, materials indexed, suggested questions](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/01-welcome.png)

Citations are first-class. Every chunk number is a chip you can click to see the source passage:

![Citations expanded — Vietnamese chunks shown inline](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/03-citations-expanded.png)

---

## Browser viewers for every supported format

Click any material in the right panel — **Original** tab renders the file natively, **Extracted** tab shows what the chunker + embedder saw. PDFs / images use the browser's native viewer; Office formats render as structured HTML so the browser can show them without LibreOffice.

| DOCX → editorial paragraphs | PPTX → 16:10 slide cards | XLSX → HTML tables with sheet picker |
|---|---|---|
| ![DOCX viewer](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/04-viewer-docx.png) | ![PPTX viewer](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/05-viewer-pptx.png) | ![XLSX viewer](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/06-viewer-xlsx.png) |

---

## Library use (no web app)

```python
from nom.rag import RAG
from nom.llm import Ollama

rag = RAG.from_documents(
    ["contract.pdf", "letter.docx", "Hợp đồng số HD-001..."],
    llm=Ollama(model="qwen3:8b"),
)

answer = rag.ask("Có bao nhiêu hợp đồng có phạt vi phạm?")
print(answer.text)         # the LLM's response
print(answer.citations)    # [(doc_idx, chunk_idx, score, text), ...]
```

Document extraction without RAG:

```python
from nom.doc import extract
from nom.llm import Ollama

result = extract(
    "hop_dong.pdf",
    schema={"so_hop_dong": str, "ngay_ky": "date", "tong_gia_tri": "amount_vnd"},
    llm=Ollama(model="qwen3:8b"),
)
```

Text utilities without the rest:

```python
from nom.text import normalize, fix_diacritics, word_tokenize

clean = normalize("Hợp đồng số 02/HĐ/2025")

# Three diacritic backends — pick by your accuracy / dependency budget:

# (1) zero-dep rule path — 41 % word acc, < 1 ms
fixed_rule = fix_diacritics("Hop dong nay duoc lap")

# (2) public Apache T5 (recommended) — 97.81 % word acc, ~150 ms on GPU
#     pip install "nom-vn[diacritic-hf]"
from nom.text.diacritic_models import HFDiacriticModel
fixed = fix_diacritics("Hop dong nay duoc lap", model=HFDiacriticModel())

# (3) pass any LLM adapter — 87-95 % depending on model
from nom.llm import Ollama
fixed_llm = fix_diacritics("Hop dong nay duoc lap", llm=Ollama("gemma3:4b"))

toks  = word_tokenize("Thành phố Hồ Chí Minh")    # ["Thành phố", "Hồ Chí Minh"]
```

---

## Install

```bash
pip install nom-vn                            # text + chunking + retrieve + rag (no I/O deps)
pip install "nom-vn[doc]"                     # + PDF / Office / OCR parsers
pip install "nom-vn[embeddings]"              # + sentence-transformers
pip install "nom-vn[llm]"                     # + httpx for Ollama / OpenAI-compat
pip install "nom-vn[chat]"                    # + FastAPI / uvicorn + everything above
pip install "nom-vn[all]"                     # the lot
```

OCR (image / scanned PDF) needs Tesseract installed system-wide:

```bash
# Debian/Ubuntu
sudo apt install tesseract-ocr tesseract-ocr-vie
# Conda
conda install -c conda-forge tesseract
# macOS
brew install tesseract tesseract-lang
```

`nom serve` auto-detects the Tesseract binary + finds `vie.traineddata`; if absent, image uploads index as zero chunks rather than failing.

---

## Architecture in one line

7 layers (Primitives / Models / Retrieval / RAG / Storage / Application / Deployment), every meaningful boundary is a `typing.Protocol`. Local single-process today; the cloud path replaces three Protocol implementations and changes nothing in the application layer.

See **[docs/architecture.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/architecture.md)** for the full layered model, Protocol seam table, and scaling-path reference.

---

## Models & datasets we publish

Apache-2.0-friendly artifacts on Hugging Face Hub (cite Viet-Anh Nguyen
and Neural Research Lab per the repo's citation block):

- 🤗 [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base) — register-balanced ViT5 fine-tune for diacritic restoration
- 🤗 [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) — 4-register diacritic evaluation grid (1,227 sentence pairs)
- 🤗 [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) — 500K Wikipedia + 150K NFC-fixed VN news training pairs

Full per-task detail: [`docs/tasks/diacritic-restoration.md`](https://github.com/nrl-ai/nom-vn/blob/main/docs/tasks/diacritic-restoration.md).

---

## Documentation

- **[docs/readme.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/readme.md)** — docs index pointing at all per-task pages
- **[docs/tasks/](https://github.com/nrl-ai/nom-vn/tree/main/docs/tasks)** — one page per task (public landscape + our pipeline + trained models + datasets + results)
- **[docs/architecture.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/architecture.md)** — the 7-layer model, Protocol seams, scaling path, anti-architecture rules
- **[docs/pipeline.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/pipeline.md)** — the document-extraction pipeline end-to-end with per-stage picks
- **[docs/benchmark.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/benchmark.md)** — measured numbers per module (the receipts behind every "Recommended stack" row above)
- **[docs/recipes.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/recipes.md)** — task-oriented "I want X, do Y" cookbook with copy-paste code
- **[docs/release.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/release.md)** — how to cut a PyPI release (Trusted Publishing via GitHub Actions, no tokens)
- **[docs/training_plan_2026q2.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/training_plan_2026q2.md)** — when to fine-tune vs adopt off-the-shelf, per component, with cost estimates
- **[docs/sota_vn_2026q2.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/sota_vn_2026q2.md)** — SOTA local LLM / embedding / OCR for Vietnamese (April 2026 snapshot, every claim cited)
- **[docs/oss_landscape_2026q2.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/oss_landscape_2026q2.md)** — OSS local-AI / RAG landscape: patterns to steal, traps to avoid
- **[benchmarks/](https://github.com/nrl-ai/nom-vn/tree/main/benchmarks)** — reproducible measurement scripts (perf + retrieval + accuracy)
- **[CONTRIBUTING.md](https://github.com/nrl-ai/nom-vn/blob/main/CONTRIBUTING.md)** — dev setup, PR rules
- **[CHANGELOG.md](https://github.com/nrl-ai/nom-vn/blob/main/CHANGELOG.md)** — version history

---

## License

Apache 2.0. Fine-tune, redistribute, commercialize freely. Please keep attribution.

## Citation

```bibtex
@software{nom2026,
  title  = {Nôm: an open Python toolkit for Vietnamese AI applications},
  author = {Nguyen, Viet-Anh and {Neural Research Lab}},
  year   = {2026},
  url    = {https://nrl.ai/nom},
  note   = {Apache 2.0}
}
```

## Built by

[Neural Research Lab](https://nrl.ai) — open-source AI tooling. Edge inference, private assistants, training, labeling.
