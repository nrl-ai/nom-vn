# Recipes — task-oriented `nom-vn` cookbook

*Last updated: 2026-04-26.*

Each recipe is a self-contained "I want X, do Y" entry. Code samples
copy-paste cleanly from a fresh `nom-vn` install. Every recommendation
points at the row in [`docs/benchmark.md`](benchmark.md) it came from —
no recipe ships an unmeasured pick.

The order of recipes follows the typical adoption arc: text utilities
→ document parsing → retrieval → RAG → chat. Skip ahead.

---

## Text recipes

### Restore Vietnamese diacritics

The single most common pre-processing step on noisy VN text (OCR output,
foreign keyboards, social-media short-form). Three backends, pick by
your accuracy budget vs dependency surface:

#### Best accuracy (97.81 % word acc, 1 GB on disk, ~150 ms GPU / ~360 ms CPU)

```bash
pip install "nom-vn[diacritic-hf]"   # transformers<5 + torch + sentencepiece
```

```python
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

restorer = HFDiacriticModel(device="cuda")  # auto-falls-back to "cpu"
out = fix_diacritics("Hop dong nay duoc lap ngay 14/3/2025", model=restorer)
# → 'Hợp đồng nay được lập ngày 14/3/2025'
```

The default model is [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base)
(ViT5-base 220 M, Apache 2.0). Pass
`model_id="nrl-ai/vn-diacritic-small"` for the lower-latency tier
(115 M, ~3× faster, ~3-4 pp word-acc trade-off), or
`model_id="nrl-ai/vn-spell-correction-base"` to get a strict superset
that also fixes letter-level typos and OCR errors.

**Register coverage** (4-register matrix, measured 2026-04-29 — see
[`docs/benchmark.md`](benchmark.md) for the full table):

| Register | Word acc |
|---|---:|
| Formal / legal-prose (UDHR) | 98.14 % |
| Business / news | 97.81 % |
| Conversational (Tatoeba) | 93.94 % |
| Classical literary (UD-VTB) | 89.40 % |

8.7 pp spread, monotonic gradient. The model is register-overfit toward
modern formal/business Vietnamese (matching its training data) but
stays usable everywhere. Failures on literary are mostly proper-noun
disambiguation (`Hùng` ↔ `Hưng` ↔ `Hứng`) and minor-register words.

#### Register-balanced alternative — `nrl-ai/vn-diacritic-vit5-base`

If your workload is heavy on **formal/legal-prose** or **conversational**
Vietnamese, our in-house ViT5-base fine-tune wins on those registers:

| Register | Toshiiiii1 | `nrl-ai/vn-diacritic-vit5-base` |
|---|---:|---:|
| Formal / legal-prose | 98.14 % | **99.43 %** ⭐ |
| Business / news | **97.81 %** | 94.98 % |
| Conversational | 93.94 % | **94.12 %** ⭐ |
| Classical literary | **89.40 %** | 90.24 % |

```python
restorer = HFDiacriticModel(model_id="nrl-ai/vn-diacritic-vit5-base")
```

Same Apache-2.0 license, same ~900 MB safetensors checkpoint, same
~150 ms/sent on a 3090. Trained on 500K Wikipedia pairs, 5 epochs
cosine LR. Pick Toshiiiii1 for business-tilted corpora; pick this one
for legal docs, government forms, or chat data. See
[`docs/benchmark.md`](benchmark.md#vn-diacritic-vit5-base) for the
full eval and training config.

#### Batched inference for throughput (7.6× speedup on a 3080)

For high-throughput pipelines (tens of thousands of sentences), use
``predict_batch`` instead of looping ``predict``:

```python
restorer = HFDiacriticModel(device="cuda")
sentences = ["Toi yeu Viet Nam", "Hop dong so 02", ...]  # 1000s
restored = restorer.predict_batch(sentences, batch_size=16)
```

Measured **7.60× throughput** vs single-call predict() on the
300-sentence Tatoeba corpus (RTX 3080 16 GB Mobile). Batch size 16 fits
in ~4 GB VRAM at typical 256-token inputs; bump to 32+ on cards with
more headroom, drop to 4–8 on smaller GPUs or for longer inputs.
Output ordering is preserved; empty/blank inputs pass through without
hitting the model.

#### Zero-deps (41 % word acc, < 1 ms)

```python
from nom.text import fix_diacritics

out = fix_diacritics("Hop dong nay duoc lap")  # no model arg → rule path
# → 'Hợp đồng này được lập' (best-effort)
```

OK for harness validation, BM25 query normalisation, low-stakes cleanup.
The accuracy floor is real — only ~41 % word acc on real VN.

#### Local LLM (87 – 93 % word acc, ~1 s/sentence)

```bash
pip install "nom-vn[llm]"
ollama pull gemma3:4b   # or gemma4:e4b, or qwen3:8b
```

```python
from nom.text import fix_diacritics
from nom.llm import Ollama

out = fix_diacritics(
    "Hop dong nay duoc lap",
    llm=Ollama(model="gemma3:4b"),
)
```

Use this when you've already wired an LLM for other tasks and want one
fewer dependency. The **`Ollama` adapter defaults to `think=False`** —
required for Qwen3, harmless for non-thinking models.

### Synthesize noisy Vietnamese text (for spell-correction training data)

`nom.text.noise` provides a deterministic noise generator that turns
clean Vietnamese sentences into realistic typo/OCR-style versions —
useful for building `(noisy, clean)` training pairs without paying for
hand-labeled data. Six tunable noise functions (diacritic strip, partial
strip, tone-confusion substitution, char swap/insert/delete, OCR
substitutions) and three calibrated presets:

```python
from nom.text.noise import NoiseGenerator, light_noise, heavy_noise, telex_typo_noise

# Light noise — models a person typing on a Vietnamese keyboard.
gen = NoiseGenerator(light_noise(), seed=42)
print(gen.noisify("Tôi yêu Việt Nam và đất nước này tuyệt vời."))
# 'Toi yêu Viet Nam và đất nước này tuyệt vời.'

# Heavy noise — models OCR output of a mid-quality scan.
gen = NoiseGenerator(heavy_noise(), seed=42)
print(gen.noisify("Hợp đồng số 02/HĐ/2025 được lập ngày 14 tháng 3 năm 2025."))
# 'Hop dong số 02/HĐ/2025 được lập ngya l4 tháng 3 năm 2025.'  # <- '14' -> 'l4'

# Telex typo — heavy diacritic perturbation, no OCR.
gen = NoiseGenerator(telex_typo_noise(), seed=42)
```

Properties:

- **Deterministic** — same `(text, config, seed)` always produces the
  same output (training-corpus reproducibility).
- **NFC-normalized output** — never returns NFD-decomposed text (the
  silent killer of seq2seq training; see [`docs/benchmark.md`][bench]
  v0.2.25 NFD-poisoning postmortem).
- **Edit-budget cap** — `max_edit_ratio` prevents pile-ups so a high-p
  config doesn't mangle the input beyond recoverability.

[bench]: https://github.com/nrl-ai/nom-vn/blob/main/docs/benchmark.md

Used by the upcoming `nrl-ai/vn-spell-correction-train` dataset. The
noise functions track the VSEC paper error taxonomy
([arxiv:2111.00640](https://arxiv.org/abs/2111.00640)) and the
high-frequency tone confusions caught in our diacritic-restoration
audits.

### Tokenize Vietnamese text

Two backends, pick by speed vs F1:

```python
# Speed-first — pure Python, zero deps, F1 76 % on UD_Vietnamese-VTB
from nom.text import word_tokenize
toks = word_tokenize("Thành phố Hồ Chí Minh là thành phố lớn nhất Việt Nam")
# ['Thành phố', 'Hồ Chí Minh', 'là', 'thành phố', 'lớn nhất', 'Việt Nam']
# 747 k tokens/sec
```

```bash
pip install "nom-vn[nlp]"   # adds underthesea
```

```python
# Quality-first — CRF model, F1 95.7 %
import underthesea
toks = underthesea.word_tokenize(
    "Thành phố Hồ Chí Minh là thành phố lớn nhất Việt Nam"
)
# 38 k tokens/sec
```

**Rule of thumb:** RAG indexing / BM25 / lightweight cleanup → `nom.text`.
NER / dependency parsing / linguistic tasks → `underthesea`.

### Normalize whitespace + Unicode

```python
from nom.text import normalize, has_diacritics, is_vietnamese

clean = normalize("Hợp  đồng   số 02/HĐ/2025  ")
# → 'Hợp đồng số 02/HĐ/2025'  (NFC + collapsed whitespace)

has_diacritics("Hợp đồng")  # True
has_diacritics("Hop dong")  # False
is_vietnamese("Hợp đồng số 02")  # True (VN-script ratio above threshold)
```

These are stdlib-only, microsecond-level. Use them in tight loops.

---

## Document parsing recipes

### Extract text from a PDF (fast path)

```bash
pip install "nom-vn[doc]"
```

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("hop_dong.pdf")
text = "\n".join(p.get_textpage().get_text_range() for p in pdf)
pdf.close()
```

`pypdfium2` (BSD-3 wrapper over Apache-2.0 PDFium) is the default in
`nom-vn[doc]`. **46× faster than pdfplumber** on plain text PDFs at
identical fidelity. Ships in our extras specifically because we won't
ship PyMuPDF — the AGPL forces every downstream into AGPL.

### Extract text *with tables* from a PDF

```python
import pdfplumber

with pdfplumber.open("invoice.pdf") as pdf:
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                print(row)
```

`pdfplumber` is slower (51 k chars/s vs pypdfium2's 2.35 M chars/s) but
has stronger table-cell detection. Both ship together in `nom-vn[doc]`.

### OCR a Vietnamese image (printed text)

```bash
sudo apt install tesseract-ocr tesseract-ocr-vie   # Debian/Ubuntu
brew install tesseract tesseract-lang              # macOS
pip install "nom-vn[doc]"
```

```python
import pytesseract
from PIL import Image

text = pytesseract.image_to_string(
    Image.open("scan.png"),
    lang="vie",
    config="--psm 6",
)
```

Tesseract 5 + `vie` hits **CER 5.53 %** on real ducto489 mid-noise
images at 80 ms p50 on 8 CPU cores. Don't reach for a vision-language
model here — `qwen2.5vl:7b` got CER 31 % at 10× the latency on the
same images (see [`docs/benchmark.md` § VLM OCR](benchmark.md)).

VLMs *are* the right tool for **complex documents** (forms, invoices,
ID cards, handwriting — wherever you want extraction *and*
understanding). They're the wrong tool for clean line transcription.

### Extract from DOCX / XLSX / PPTX

```python
from docx import Document
doc = Document("contract.docx")
for para in doc.paragraphs:
    print(para.text)
```

```python
import openpyxl
wb = openpyxl.load_workbook("data.xlsx")
for sheet in wb.sheetnames:
    for row in wb[sheet].iter_rows(values_only=True):
        print(row)
```

```python
from pptx import Presentation
prs = Presentation("deck.pptx")
for slide in prs.slides:
    for shape in slide.shapes:
        if shape.has_text_frame:
            print(shape.text_frame.text)
```

All MIT/Apache, all pure-Python, all in `nom-vn[doc]`.

### One-line: any-format → text

```python
from nom.doc import Pipeline

pipeline = Pipeline()  # auto-detects format
result = pipeline.run("anything.pdf").text   # or .docx, .xlsx, .pptx, .png, .html
```

---

## Retrieval recipes

### Build a Vietnamese RAG index — high-quality config

The choice of embedder dominates retrieval quality on VN. Use the
retrieval-trained embedder, not the STS-trained default:

```bash
pip install "nom-vn[embeddings,nlp]"   # adds sentence-transformers + underthesea
```

```python
from nom.embeddings import BKaiEmbedder
from nom.retrieve import DenseRetriever, BM25Retriever, HybridRetriever

embedder = BKaiEmbedder(device="cuda")   # or "cpu", "mps"
docs = ["Hợp đồng số 02/HĐ/2025...", "Đối tác A: Công ty Cổ phần..."]

dense = DenseRetriever(embedder=embedder)
dense.fit(docs)
hits = dense.search("hợp đồng có phạt vi phạm không?", top_k=5)
```

**Why bkai not dangvantuan?** On Zalo Legal QA 5 k:

- `bkai-foundation-models/vietnamese-bi-encoder`: R@1 76.25 %, R@10 98.75 %
- `dangvantuan/vietnamese-embedding`: R@1 35.00 %, R@10 67.50 %

bkai trained with `MultipleNegativesRankingLoss` on Q→Doc retrieval pairs;
dangvantuan trained on STS (symmetric similarity) — wrong task. The
bkai model auto-applies underthesea word segmentation (multi-syllable
words joined with `_`) so you don't have to.

### Hybrid retrieval (BM25 + dense)

```python
from nom.retrieve import BM25Retriever, DenseRetriever, HybridRetriever

bm25 = BM25Retriever()
bm25.fit(docs)

dense = DenseRetriever(embedder=BKaiEmbedder())
dense.fit(docs)

hybrid = HybridRetriever([bm25, dense])
hits = hybrid.search("…", top_k=10)
```

Hybrid uses Reciprocal Rank Fusion. On the full Zalo Legal 61 k corpus:

| Stage | recall@10 |
|---|---:|
| BM25 alone | 0.78 |
| Dense alone (`dangvantuan`) | 0.54 |
| Hybrid RRF | 0.78 |
| **Hybrid + reranker** | **0.87** |

BM25 is **shockingly competitive** at small corpus sizes (5 k subset
hits R@1 = 0.76) but the dense + reranker stages get more important as
the distractor pool grows.

### Add cross-encoder reranking

```bash
pip install "nom-vn[reranker]"
```

```python
from nom.rag import RAG
from nom.embeddings import BKaiEmbedder
from nom.llm import Ollama

rag = RAG.from_documents(
    docs,
    embedder=BKaiEmbedder(device="cuda"),
    llm=Ollama(model="qwen3:8b"),
    rerank=True,            # adds BAAI/bge-reranker-v2-m3 by default
    rerank_candidates=30,   # rerank top-30 from hybrid
    rerank_keep=5,          # pass top-5 to LLM
)
answer = rag.ask("Trong các hợp đồng đã ký, có điều khoản phạt nào?")
```

The default reranker is `BAAI/bge-reranker-v2-m3` (Apache, 568 M).
Brings R@1 to ~86 % on Zalo Legal 5 k. `namdp-ptit/ViRanker` (Apache,
600 M, VN-specialized) is within 1.3 pp — pass `reranker="namdp-ptit/ViRanker"`
if you want the VN-tuned variant.

### Fast BM25 over a big corpus

```python
from nom.retrieve import BM25Retriever

bm25 = BM25Retriever()
bm25.fit(corpus_of_60k_docs)   # ~5 seconds for 60k legal articles
hits = bm25.search("Trình tự thỏa thuận thông số kỹ thuật...", top_k=10)
# 0.7 ms per query — backed by bm25s (Lucene formula, scipy.sparse)
```

The v0.2.6 swap to `bm25s` was a **607× speedup** with bit-identical
recall vs the v0.2.5 pure-Python implementation. No quality cost.

---

## RAG recipes

### One-line RAG over local documents

```python
from nom.rag import RAG
from nom.llm import Ollama

rag = RAG.from_documents(
    ["contract.pdf", "letter.docx", "Hợp đồng số HD-001..."],
    llm=Ollama(model="qwen3:8b"),
)

answer = rag.ask("Có bao nhiêu hợp đồng có phạt vi phạm?")
print(answer.text)
print(answer.citations)   # [(doc_idx, chunk_idx, score, text), ...]
```

The default uses `dangvantuan/vietnamese-embedding` for cache
compatibility. **Override to `BKaiEmbedder` for +41 pp R@1 on retrieval:**

```python
from nom.embeddings import BKaiEmbedder

rag = RAG.from_documents(
    docs,
    embedder=BKaiEmbedder(device="cuda"),
    llm=Ollama(model="qwen3:8b"),
)
```

The 0.3.x major release will switch the default to bkai. We don't flip
mid-version because it would silently invalidate users' persisted
embedding caches.

### Structured extraction (no RAG)

```python
from nom.doc import extract
from nom.llm import Ollama

result = extract(
    "hop_dong.pdf",
    schema={
        "so_hop_dong": str,
        "ngay_ky": "date",
        "tong_gia_tri": "amount_vnd",
        "ben_a": str,
        "ben_b": str,
    },
    llm=Ollama(model="qwen3:8b"),
)

print(result.so_hop_dong, result.ngay_ky, result.tong_gia_tri)
```

`extract` parses → chunks → asks the LLM with structured-output
constraint (Ollama `format` JSON schema). The LLM never sees raw PDF
bytes; it only sees the cleaned text + the schema.

### Use a different LLM provider

The `LLM` Protocol is one method (`complete(prompt, *, schema=None)`).
Three adapters ship:

```python
# Ollama (local) — default think=False
from nom.llm import Ollama
llm = Ollama(model="gemma3:4b")

# OpenAI / OpenAI-compatible (DeepSeek, Together, Groq, vLLM…)
from nom.llm import OpenAI
llm = OpenAI(model="gpt-4o-mini")
llm = OpenAI(model="deepseek-chat", base_url="https://api.deepseek.com")

# Anthropic
from nom.llm import Anthropic
llm = Anthropic(model="claude-haiku-4-5")
```

Any class with `complete(prompt, *, schema, max_tokens) -> str` works
as an `LLM`. Roll your own for vLLM, LiteLLM, custom HTTP, etc.

---

## Chat web app recipes

### Run the chat app locally

```bash
pip install "nom-vn[chat]"
ollama pull qwen3:8b
nom serve
# → http://localhost:8080
```

Upload PDF/Word/Excel/PowerPoint/images, ask in Vietnamese, get answers
with click-to-source citations. Persistent at `~/.nom`.

### Run ephemeral (no disk persistence)

```bash
nom serve --in-memory
```

Useful for demos, CI, or when you don't want the SQLite file. All
spaces / chats / docs vanish on `Ctrl+C`.

### Custom port / model

```bash
nom serve --port 9000 --model phi4
```

### Programmatic use of the same store

```python
from nom.chat.stores import MemoryStore   # or SqliteStore("./nom.db")
from nom.embeddings import BKaiEmbedder
from nom.llm import Ollama

store = MemoryStore(embedder=BKaiEmbedder(), llm=Ollama())
space_id = store.create_space("My contracts")
store.add_document(space_id, "contract.pdf")
answer = store.ask(space_id, "Tóm tắt nội dung hợp đồng?")
```

---

## Operations recipes

### Reproduce a bench number

Every "measured" claim in the docs has a runnable script:

```bash
# Diacritic restoration on the public 55-sent corpus
python benchmarks/accuracy/bench_diacritics.py
python benchmarks/accuracy/bench_diacritic_hf.py \
    Toshiiiii1/Vietnamese_diacritics_restoration_5th

# Word segmentation on UD_Vietnamese-VTB test (gold)
python benchmarks/accuracy/bench_segment.py --corpus ud_vtb --split test

# OCR on real ducto489 mid-noise corpus
python benchmarks/accuracy/bench_ocr_real.py \
    --corpus benchmarks/data/vn_ocr_subset --variant none \
    --engines tesseract,easyocr --limit 50

# RAG retrieval on Zalo Legal QA
python benchmarks/rag/bench_rag_vn.py --embedder bkai
python benchmarks/rag/bench_embedder_compare.py
```

Baselines under `benchmarks/results/baseline_*.json`. Reproducibility
is a our verified-benchmarks rule hard rule — every number must come from a script
runnable from a clean clone, not a model-card screenshot.

### See what changed between releases

```bash
git log --oneline v0.2.6..HEAD     # since the BM25 swap
```

CHANGELOG.md has per-version detail with the measured numbers that
moved.

### Verify license compliance for shipped deps

```bash
pip-licenses --format=markdown --packages nom-vn pypdfium2 pdfplumber \
    sentence-transformers underthesea bm25s
```

We refuse AGPL (PyMuPDF, Surya), GPL (Surya code), and pickle-shipping
deps (PyVi). The auto-rejection list is in our component-build policy.

---

## See also

- [`docs/architecture.md`](architecture.md) — the 7-layer model + Protocol seams
- [`docs/benchmark.md`](benchmark.md) — every measured number in this
  document, with methodology
- [`docs/training_plan_2026q2.md`](training_plan_2026q2.md) — when to
  fine-tune vs adopt off-the-shelf
- [`docs/sota_vn_2026q2.md`](sota_vn_2026q2.md) — current VN SOTA picks
  per task with citations
- [`CHANGELOG.md`](../CHANGELOG.md) — per-version detail
