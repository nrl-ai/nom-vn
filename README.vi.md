# Nôm 喃

**Bộ công cụ Python mã nguồn mở để xây dựng ứng dụng AI tiếng Việt.**

> Đặt theo tên *chữ Nôm* — bộ chữ Việt Nam dùng suốt một thiên niên kỷ.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/nrl-ai/nom-vn/blob/main/LICENSE)
[![Trạng thái](https://img.shields.io/badge/status-v0.2.26-orange)](https://github.com/nrl-ai/nom-vn/blob/main/CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-354%20passing-brightgreen)](https://github.com/nrl-ai/nom-vn/tree/main/tests)

Bộ công cụ ưu tiên local. **Dữ liệu không rời khỏi máy của bạn.** Dùng bất kỳ LLM nào (mặc định Ollama), bất kỳ embedder nào, bất kỳ định dạng tài liệu nào — Nôm gói chúng vào pipeline RAG hiểu tiếng Việt mà bạn có thể ship dưới dạng thư viện Python hoặc web app chat triển khai sẵn.

**Mỗi cấu hình mặc định đều được benchmark trên dữ liệu tiếng Việt thực.** Khi mô hình Apache/MIT công khai vượt mô hình đa ngôn ngữ, chúng tôi dùng nó. Xem [docs/benchmark.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/benchmark.md) để có toàn bộ số liệu.

---

## Demo 3 dòng

```bash
pip install "nom-vn[chat]"     # FastAPI + React UI + parser + embeddings
nom serve                       # mở http://localhost:8080
# upload PDF/Word/Excel/PowerPoint/ảnh, hỏi đáp bằng tiếng Việt
```

![Nôm — chat với trích dẫn dựa trên tài liệu tiếng Việt được index](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/02-chat-with-answer.png)

Web app được build sẵn vào wheel — không cần cài thêm gì.

---

## Cấu hình khuyến nghị — *đo ngày 2026-04-30*

Mỗi đề xuất đều có số đo từ script trong
[`benchmarks/`](https://github.com/nrl-ai/nom-vn/tree/main/benchmarks) chạy được trên bản clone sạch. Không có số ước tính.
Không có "dựa trên model card." Số liệu lấy từ phần cứng của chúng tôi,
trên ngữ liệu tiếng Việt thực, trong tuần này.

| Tác vụ | Lựa chọn | Giấy phép | Dung lượng | Đo được | Vượt qua |
|---|---|---|---:|---|---|
| **Khôi phục dấu (mặc định)** [→](https://github.com/nrl-ai/nom-vn/blob/main/docs/tasks/diacritic-restoration.md) | `Toshiiiii1/Vietnamese_diacritics_restoration_5th` (T5 200 M, opt-in) | Apache 2.0 | 1 GB | **97.81 %** word acc trên kinh doanh · 89.40 % văn học · 98.14 % trang trọng · 93.94 % hội thoại | vượt cloud `gpt-4o-mini` 95.37 % trên kinh doanh; SOTA trên ma trận 4 thể loại |
| **Khôi phục dấu (cân bằng thể loại)** [→](https://github.com/nrl-ai/nom-vn/blob/main/docs/tasks/diacritic-restoration.md) | [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base) (ViT5 220 M, của chúng tôi) | Apache 2.0 | 900 MB | 99.43 % trang trọng (+1.29 pp) · 94.12 % hội thoại (+0.18 pp) · 94.98 % kinh doanh (-2.83) · 90.24 % văn học | thắng trang trọng + hội thoại; chọn cho văn bản pháp lý / dữ liệu chat, Toshiiiii1 cho văn bản kinh doanh |
| **Khôi phục dấu (zero-dep dự phòng)** | bảng quy tắc (`nom.text.fix_diacritics`) | Apache 2.0 | 0 | 41.06 % word acc · <1 ms | — |
| **Khôi phục dấu (LLM local)** | `gemma3:4b` Q4 qua Ollama | Apache 2.0 | 3.3 GB | 87.90 % word acc · 1.10 s | `qwen3:8b` (87.26 %), `gemma4:e4b` cao hơn +5pp nhưng lớn 3× |
| **Tách từ (tốc độ)** | `nom.text.word_tokenize` (rule, zero deps) | Apache 2.0 | 0 | F1 76.46 % · 747 k tok/s | — |
| **Tách từ (chất lượng)** | `underthesea` 9.4.0 (CRF, opt-in) | Apache 2.0 | <10 MB | F1 95.70 % · 38 k tok/s | khớp với số liệu VLSP 2013 đã công bố |
| **OCR (dòng in sạch)** | Tesseract 5 + `vie` traineddata | Apache 2.0 | ~30 MB | CER 5.53 % · 80 ms p50 | EasyOCR (9.39 %), `qwen2.5vl:7b` (31.07 %) |
| **Trích văn bản PDF** | `pypdfium2` (BSD-3 wrap PDFium Apache-2.0) | BSD-3 / Apache | <10 MB | 99.81 % char overlap · 2.35 M chars/s | `pdfplumber` (51 k chars/s), Docling (15 k chars/s) |
| **Dense embedder (RAG)** | `bkai-foundation-models/vietnamese-bi-encoder` (opt-in) | Apache 2.0 | 383 MB | R@1 76.25 % · R@10 98.75 % trên Zalo Legal QA 5 k | `dangvantuan/vietnamese-embedding` (35.00 % R@1) hơn +41.25 pp |
| **Dense embedder (mặc định, ổn định)** | `dangvantuan/vietnamese-embedding` | Apache 2.0 | 440 MB | R@1 35.00 % trên Zalo Legal QA 5 k | — |
| **Reranker** | `BAAI/bge-reranker-v2-m3` | Apache 2.0 | ~2 GB | R@1 86.3 % kết hợp dense (Zalo Legal 5 k) | `namdp-ptit/ViRanker` (85.0 %) |
| **BM25** | `bm25s` (công thức Lucene) | MIT | <10 MB | R@1 76.2 % trên Zalo Legal 5 k · 0.7 ms/query | nhanh 607× so với pure-Python v0.2.5 |

**Quyết định ngắn gọn:**

- *Cần khôi phục dấu tiếng Việt?* Cài `nom-vn[diacritic-hf]` và dùng Toshiiiii1 T5. Vượt cloud GPT-4o-mini.
- *Cần RAG local trên tài liệu tiếng Việt?* Cài `nom-vn[chat,embeddings,nlp]`, đổi embedder mặc định sang `BKaiEmbedder`. +41 pp R@1.
- *Cần OCR ảnh quét tiếng Việt?* Tesseract `vie` là lựa chọn đúng. Đừng dùng VLM cho OCR — VLM thường ảo giác trên crop dòng hẹp.
- *Cần trích văn bản PDF không vướng giấy phép?* Dùng `pypdfium2` (đã ship sẵn). Tránh PyMuPDF — AGPL của nó kéo mọi thứ downstream thành AGPL.

## Đang ship hôm nay

| Module | Chức năng | Trạng thái |
|---|---|---|
| `nom.text` | NFC normalize, khôi phục dấu rule-based, tách từ. Ngoài ra: `HFDiacriticModel` (Toshiiiii1 T5, 97.81 %, opt-in), `nom.text.noise` (sinh nhiễu cho training spell-correction) | ✅ |
| `nom.chunking` | Chunking tài liệu hiểu tiếng Việt | ✅ |
| `nom.embeddings` | Protocol `Embedder` + `VietnameseEmbedder` (mặc định) + `BKaiEmbedder` (khuyến nghị, train cho retrieval) + `AITeamVNEmbedder` (BGE-M3 ft) | ✅ |
| `nom.retrieve` | `BM25Retriever` (bm25s, nhanh 607× so với v0.2.5), `DenseRetriever`, hybrid RRF fusion | ✅ |
| `nom.doc` | PDF (`pypdfium2` nhanh 46× so với pdfplumber) / DOCX / XLSX / PPTX / HTML / ảnh (Tesseract OCR) → text | ✅ |
| `nom.llm` | Protocol `LLM` + adapter `Ollama` (mặc định `think=False`) + `OpenAI` + `Anthropic` | ✅ |
| `nom.rag` | Compose RAG một dòng + cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) | ✅ |
| `nom.chat` | FastAPI server + React/ShadCN UI, `MemoryStore` + `SqliteStore` + `EmbeddingsCache` cắm-rời được | ✅ |

---

## Web app Q&A tài liệu kiểu NotebookLM

Bố cục biên tập 3 cột: sidebar không gian / luồng chat / nguồn + studio. Bảng màu biên tập tối, góc cạnh sắc, truy vết citation đầy đủ.

Bố cục 3 cột (desktop 1920×1080):

![Khung chat mặc định — chọn space, tài liệu đã index, câu hỏi gợi ý](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/01-welcome.png)

Citation là công dân hạng nhất. Mỗi số chunk là chip có thể click để xem đoạn nguồn:

![Citation mở rộng — chunk tiếng Việt hiển thị inline](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/03-citations-expanded.png)

---

## Trình xem tài liệu trực tiếp trên trình duyệt

Click bất kỳ tài liệu nào ở panel phải — tab **Original** render file gốc, tab **Extracted** hiển thị những gì chunker + embedder đã thấy. PDF / ảnh dùng trình xem mặc định của trình duyệt; định dạng Office render thành HTML có cấu trúc để trình duyệt hiển thị mà không cần LibreOffice.

| DOCX → đoạn văn biên tập | PPTX → thẻ slide 16:10 | XLSX → bảng HTML có chọn sheet |
|---|---|---|
| ![DOCX viewer](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/04-viewer-docx.png) | ![PPTX viewer](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/05-viewer-pptx.png) | ![XLSX viewer](https://raw.githubusercontent.com/nrl-ai/nom-vn/main/docs/screenshots/06-viewer-xlsx.png) |

---

## Dùng như thư viện (không web app)

```python
from nom.rag import RAG
from nom.llm import Ollama

rag = RAG.from_documents(
    ["contract.pdf", "letter.docx", "Hợp đồng số HD-001..."],
    llm=Ollama(model="qwen3:8b"),
)

answer = rag.ask("Có bao nhiêu hợp đồng có phạt vi phạm?")
print(answer.text)         # phản hồi của LLM
print(answer.citations)    # [(doc_idx, chunk_idx, score, text), ...]
```

Trích xuất tài liệu không cần RAG:

```python
from nom.doc import extract
from nom.llm import Ollama

result = extract(
    "hop_dong.pdf",
    schema={"so_hop_dong": str, "ngay_ky": "date", "tong_gia_tri": "amount_vnd"},
    llm=Ollama(model="qwen3:8b"),
)
```

Tiện ích text độc lập:

```python
from nom.text import normalize, fix_diacritics, word_tokenize

clean = normalize("Hợp đồng số 02/HĐ/2025")

# Ba backend khôi phục dấu — chọn theo ngân sách độ chính xác / dependency:

# (1) rule zero-dep — 41 % word acc, < 1 ms
fixed_rule = fix_diacritics("Hop dong nay duoc lap")

# (2) Apache T5 công khai (khuyến nghị) — 97.81 % word acc, ~150 ms trên GPU
#     pip install "nom-vn[diacritic-hf]"
from nom.text.diacritic_models import HFDiacriticModel
fixed = fix_diacritics("Hop dong nay duoc lap", model=HFDiacriticModel())

# (3) truyền adapter LLM bất kỳ — 87-95 % tuỳ mô hình
from nom.llm import Ollama
fixed_llm = fix_diacritics("Hop dong nay duoc lap", llm=Ollama("gemma3:4b"))

toks  = word_tokenize("Thành phố Hồ Chí Minh")    # ["Thành phố", "Hồ Chí Minh"]
```

---

## Cài đặt

```bash
pip install nom-vn                            # text + chunking + retrieve + rag (không I/O deps)
pip install "nom-vn[doc]"                     # + parser PDF / Office / OCR
pip install "nom-vn[embeddings]"              # + sentence-transformers
pip install "nom-vn[llm]"                     # + httpx cho Ollama / OpenAI-compat
pip install "nom-vn[chat]"                    # + FastAPI / uvicorn + tất cả ở trên
pip install "nom-vn[all]"                     # toàn bộ
```

OCR (ảnh / PDF scan) cần Tesseract cài system-wide:

```bash
# Debian/Ubuntu
sudo apt install tesseract-ocr tesseract-ocr-vie
# Conda
conda install -c conda-forge tesseract
# macOS
brew install tesseract tesseract-lang
```

`nom serve` tự dò binary Tesseract + tìm `vie.traineddata`; nếu không có, ảnh upload sẽ index 0 chunk thay vì lỗi.

---

## Kiến trúc trong một dòng

7 lớp (Primitives / Models / Retrieval / RAG / Storage / Application / Deployment), mọi ranh giới có ý nghĩa đều là một `typing.Protocol`. Hôm nay chạy single-process local; đường tới cloud chỉ thay 3 implementation Protocol và không động đến lớp ứng dụng.

Xem **[docs/architecture.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/architecture.md)** để có mô hình phân lớp đầy đủ, bảng Protocol seam, và tham chiếu đường mở rộng.

---

## Mô hình & dataset đã publish

Mô hình + dataset của chúng tôi trên Hugging Face Hub
(Apache-2.0 trở xuống, có ghi công Nguyễn Việt Anh + Neural Research Lab):

- 🤗 [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base) — fine-tune ViT5-base khôi phục dấu, cân bằng thể loại
- 🤗 [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) — dataset đánh giá khôi phục dấu 4 thể loại (1,227 cặp câu)
- 🤗 [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) — 500K wiki + 150K news (NFC) cặp training

Chi tiết: [`docs/tasks/diacritic-restoration.md`](https://github.com/nrl-ai/nom-vn/blob/main/docs/tasks/diacritic-restoration.md).

---

## Tài liệu

- **[docs/readme.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/readme.md)** — chỉ mục tài liệu (trỏ tới các trang per-task)
- **[docs/tasks/](https://github.com/nrl-ai/nom-vn/tree/main/docs/tasks)** — một trang cho mỗi tác vụ (landscape công khai + pipeline + mô hình + dataset + kết quả)
- **[docs/architecture.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/architecture.md)** — mô hình 7 lớp, Protocol seams, đường mở rộng, anti-pattern
- **[docs/pipeline.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/pipeline.md)** — pipeline trích xuất tài liệu end-to-end với từng stage
- **[docs/benchmark.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/benchmark.md)** — số đo per module (chứng cứ sau mỗi dòng "Recommended stack" ở trên)
- **[docs/recipes.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/recipes.md)** — cookbook "tôi muốn X, làm Y" với code copy-paste
- **[docs/release.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/release.md)** — cách cut release PyPI (Trusted Publishing qua GitHub Actions, không cần token)
- **[docs/training_plan_2026q2.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/training_plan_2026q2.md)** — khi nào fine-tune vs adopt off-the-shelf, theo từng component, kèm ước tính chi phí
- **[docs/sota_vn_2026q2.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/sota_vn_2026q2.md)** — SOTA LLM / embedding / OCR cho tiếng Việt (snapshot tháng 4/2026, mọi claim có citation)
- **[docs/oss_landscape_2026q2.md](https://github.com/nrl-ai/nom-vn/blob/main/docs/oss_landscape_2026q2.md)** — landscape OSS local-AI / RAG: pattern nên copy, bẫy nên tránh
- **[benchmarks/](https://github.com/nrl-ai/nom-vn/tree/main/benchmarks)** — script đo lường có thể tái lập (perf + retrieval + accuracy)
- **[CONTRIBUTING.md](https://github.com/nrl-ai/nom-vn/blob/main/CONTRIBUTING.md)** — setup dev, quy tắc PR
- **[CHANGELOG.md](https://github.com/nrl-ai/nom-vn/blob/main/CHANGELOG.md)** — lịch sử phiên bản

---

## Giấy phép

Apache 2.0. Fine-tune, redistribute, thương mại hoá tự do. Vui lòng giữ ghi công.

## Trích dẫn

```bibtex
@software{nom2026,
  title  = {Nôm: an open Python toolkit for Vietnamese AI applications},
  author = {Nguyen, Viet-Anh and {Neural Research Lab}},
  year   = {2026},
  url    = {https://nrl.ai/nom},
  note   = {Apache 2.0}
}
```

## Phát triển bởi

[Nguyễn Việt Anh](mailto:vietanh@nrl.ai) & [Neural Research Lab](https://nrl.ai).
