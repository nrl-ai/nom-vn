# SOTA cho AI tiếng Việt cục bộ — Snapshot 2026 Q2

**Phạm vi.** Ba lớp của `nom-vn`: LLM cục bộ, embedding text dense, OCR tài liệu.
**Ràng buộc.** License Apache-2.0-friendly, không có weights pickle, chạy được trên laptop hoặc một GPU consumer (≤24 GB VRAM, lý tưởng ≤8 GB ở mức mặc định), chất lượng tiếng Việt có nguồn benchmark.
**Ngày.** 2026-04-25. Mọi con số bên dưới đều có URL hoạt động; chỗ nào không có chúng tôi nói rõ.

---

## 1. LLM (sinh văn bản cục bộ)

### Giữ `Qwen3-8B`, thêm `Sailor2-8B` làm bản VN-tuned thay thế

| Tier | Mô hình | License | Disk (BF16 / Q4) | VRAM tối thiểu | Benchmark VN |
|---|---|---|---:|---:|---|
| **Mặc định** | `Qwen/Qwen3-8B` | Apache 2.0 | ~16 GB / ~5 GB | 6 GB (Q4) / 16 GB (BF16) | Không có số VN first-party trên model card; không có trên VMLU leaderboard tính đến 2026-04-25 |
| **VN-tuned thay thế** | `sail/Sailor2-8B` | Apache 2.0 | ~18 GB BF16 | ~16 GB | 13 ngôn ngữ SEA bao gồm VN; tác giả tự gọi là "best multilingual <10 B for SEA" |
| **One down** | `sail/Sailor2-1B` | Apache 2.0 | ~2 GB | ~3 GB / chạy CPU được | Cùng mix SEA ở quy mô 1 B |
| **One up** | `sail/Sailor2-20B` | Apache 2.0 | ~40 GB BF16 / ~12 GB Q4 | 24 GB (Q4) | Tác giả công bố ~50/50 win-rate so với GPT-4o trên ngôn ngữ SEA (bảng đầy đủ trong paper) |

Nguồn: [Qwen3-8B card](https://huggingface.co/Qwen/Qwen3-8B), [blog Sailor2](https://sea-sailor.github.io/blog/sailor2/), [paper Sailor2 (arXiv 2502.12982)](https://arxiv.org/abs/2502.12982), [VMLU leaderboard](https://vmlu.ai/leaderboard).

**Các ứng viên khác.** **PhoGPT-4B** ([HF](https://huggingface.co/vinai/PhoGPT-4B), BSD-3, 3.7 B, VinAI 2024) — không có cập nhật 2025/2026; cũ. **Vistral-7B-Chat** ([HF](https://huggingface.co/Viet-Mistral/Vistral-7B-Chat)) — paper công bố VMLU **50.07** vs ChatGPT 46.33, nhưng card HF không nêu rõ giấy phép thương mại. **Phi-4** (MIT, 14 B) — không có benchmark VN công bố; chỉ chấp nhận làm headroom. Top VMLU bị các bản fine-tune VN closed thống trị (axis-sovereign 85.75, V-LLM v1 85.11, MISA-AI-1.0 81.26) — không liên quan với hướng cục bộ.

**6 tháng gần nhất.** Họ Qwen3 (32K ctx native, 131K YaRN) đã thay Qwen2.5 làm LLM mặc định open SEA-friendly. **Sailor2** (02/2025) trở thành họ *VN-tuned, redistributable* mạnh nhất ở quy mô 1 B/8 B/20 B — Apache challenger đáng tin đầu tiên cho PhoGPT/Vistral. PhoGPT và Vistral đều thực tế đã ngừng phát triển.

**Cạm bẫy VN.** Dấu thanh (â/ă/ê/ô/ơ/ư + 5 thanh) bị cắt thành 3–6 token/từ trong BPE nếu không có exposure VN — Qwen3 và Sailor2 đều ổn. Register pháp lý / tài chính mỏng trong pretraining; mục "Law" trên VMLU thể hiện gap open-vs-closed lớn nhất. Mô hình ≤4 B rớt dấu trên các danh từ riêng hiếm.

**Khuyến nghị.** Giữ `qwen3:8b` mặc định. **Thêm `sail/Sailor2-8B`** dưới dạng "VN-tuned alternative" có tài liệu. Phi-4 và Sailor2-20B Q4 cho tier accurate. Bỏ Vistral cho tới khi license rõ.

---

## 2. Embedding (dense retrieval)

### Đổi mặc định từ `dangvantuan/vietnamese-embedding` sang `AITeamVN/Vietnamese_Embedding`

`dangvantuan/vietnamese-embedding` là bản fine-tune **BGE-base** (~440 MB, 768-d). `AITeamVN/Vietnamese_Embedding` là fine-tune **BGE-M3** (~2.3 GB, 1024-d). Bản sau thắng mọi đánh giá VN công khai chúng tôi tìm được. Mức tăng size có thể chấp nhận được cho tier mặc định.

| Tier | Mô hình | License | Dim / Size | Benchmark VN |
|---|---|---|---|---|
| **One down (CPU)** | `dangvantuan/vietnamese-embedding` | Apache 2.0 | 768-d, ~440 MB | Mặc định hiện tại; không có trong VN-MTEB Bảng 3 |
| **One down thay thế** | `hiieu/halong_embedding` | Apache 2.0 | 768-d (Matryoshka 64–768), ~0.3 B | Acc@1 **0.8294**, MRR@10 **0.8799** trên Zalo Legal (giữ lại 20 %) |
| **Mặc định** | `AITeamVN/Vietnamese_Embedding` | Apache 2.0 | 1024-d, ~2.3 GB, 2048 ctx | Acc@1 **0.7274 vs 0.5682** so với BGE-M3 base, MRR@10 **0.8181 vs 0.6822** trên Zalo Legal — **+27.9 % Acc@1** |
| **Default ref** | `BAAI/bge-m3` | MIT | 1024-d, ~2.3 GB | VN-MTEB **tổng 64.90** (Retr 39.84 / Cls 69.09 / Pair 84.43 / Clust 45.90 / Rerank 71.28 / STS 78.84) |
| **One up** | `intfloat/multilingual-e5-large-instruct` | MIT | 1024-d, ~2.2 GB | VN-MTEB **tổng 67.99** — model APE tốt nhất trong paper |
| **One up thay thế** | `intfloat/e5-mistral-7b-instruct` | MIT | 4096-d, ~14 GB | VN-MTEB **tổng 67.67**, Pair-class **84.01**, STS **81.20** — top model RoPE |

Nguồn: [VN-MTEB Bảng 3 (arXiv 2507.21500)](https://arxiv.org/html/2507.21500v1), [card AITeamVN HF](https://huggingface.co/AITeamVN/Vietnamese_Embedding), [card halong HF](https://huggingface.co/hiieu/halong_embedding).

**Mâu thuẫn cần flag.** `BENCHMARK.md` của chúng tôi nói "BGE-M3 #1 ở 64.90 tổng" trên VN-MTEB. **Thực tế #1 trong Bảng 3 là `m-e5-large-instruct` ở 67.99**, với `e5-mistral-7b-instruct` (67.67) và `gte-Qwen2-7B-instruct` (65.84) trên BGE-M3. BGE-M3 đại khái ở vị trí thứ 4. Sửa trước khi user phát hiện.

**Mô hình AITeamVN có thực sự cạnh tranh hay chỉ marketing?** Số Zalo Legal tái lập được từ card HF trên split giữ lại 20 % (mô hình không train trên đó). +27.9 % Acc@1 so với BGE-M3 base trên corpus pháp lý VN là thật. Nhưng mô hình *không* được xếp riêng trong VN-MTEB Bảng 3 — entry "Vietnamese-Embedding" 63.34 trong paper có vẻ trỏ tới `dangvantuan/vietnamese-embedding`, không phải AITeamVN. Coi gain của AITeamVN là verified trên retrieval pháp lý, chưa verify trên VN-MTEB rộng hơn.

**6 tháng gần nhất.** **Paper VN-MTEB** (07/2025) — benchmark VN 41-dataset, 6-task xuất bản đầu tiên; framework tham chiếu đi tới. **`5CD-AI/Vintern-Embedding-1B`** và **`ColVintern-1B-v1`** — retrieval VN multimodal, không có số VN-MTEB ([HF org](https://huggingface.co/5CD-AI)). **Vietnamese_Reranker** của AITeamVN (Acc@1 **0.7944** trên Zalo Legal) là ứng viên retrieve+rerank mạnh.

**Cạm bẫy VN.** BGE-base tokenize VN kém rõ rệt so với BGE-M3 và nhạy hơn với NFC/NFD — luôn normalize về NFC khi ingest (`nom.text` đã làm). Số Zalo Legal không transfer tuyến tính sang news/conversational; đo lại trên corpus của bạn. 2048 ctx của AITeamVN khá rộng; phần lớn paragraph pháp lý VN dài 200–400 token — over-chunking không tăng recall mà tốn chi phí.

**Khuyến nghị.** Promote `AITeamVN/Vietnamese_Embedding` lên mặc định; giữ bản hiện tại làm `lite`. Document `e5-mistral-7b-instruct` làm tier nặng. **Sửa claim "BGE-M3 #1".**

---

## 3. OCR (ảnh / PDF scan → text)

Lớp lộn xộn nhất. **Không có VLM-as-OCR license Apache nào có benchmark VN công bố mà chúng tôi verify được.** Chúng tôi chọn dựa trên bằng chứng kế cận (điểm multilingual, subset Latin-script, độ phủ ngôn ngữ).

| Tier | Hệ thống | License | Size / phần cứng | Số đã verify |
|---|---|---|---|---|
| **One down (CPU)** | Tesseract 5 + `vie` | Apache 2.0 | ~30 MB, CPU | Không có số SOTA; baseline ~70–97 % phụ thuộc đầu vào. Lỗi stacked-diacritic đã được tài liệu hoá. |
| **Mặc định** | PaddleOCR PP-OCRv5 | Apache 2.0 | <100 MB det+rec, CPU/GPU | VN nằm trong list 106 ngôn ngữ; **>30 %** gain nhận dạng multilingual so với PP-OCRv3, +13 % so với PP-OCRv4 (không có số VN per-language) |
| **Mặc định thay thế** | VietOCR (pbcquoc) | Apache 2.0 | ~100 MB, recommend GPU | Train trên **10 M ảnh VN**; không có benchmark peer-reviewed; repo dormant 2025–2026 |
| **Accurate** | `rednote-hilab/dots.ocr` (3 B VLM) | **MIT** | 3 B, safetensors, ~6 GB, vừa 8–12 GB VRAM | OmniDocBench-EN edit **0.125** (thắng Gemini-2.5-Pro 0.148, MinerU 2 0.139); bench in-house 100 ngôn ngữ **nhưng không có điểm VN per-language** |
| **Accurate thay thế** | `Qwen/Qwen3-VL-8B-Instruct` | Apache 2.0 | 9 B, safetensors, ~18 GB BF16 / ~6 GB Q4 | Officially support **32 ngôn ngữ gồm tiếng Việt** (tăng từ 19 ở Qwen2.5-VL); robust với blur/tilt; không có số OCR VN-specific trên card |
| **Reference (closed)** | Datalab Chandra ("Accurate") | proprietary | API hoặc self-host | Datalab tổng **1798**, vs dots.ocr **1489**, olmOCR 2 **1387**, DeepSeek-OCR **1336** — VN không có trong các bảng per-language nhìn thấy được |

Nguồn: [dots.ocr HF](https://huggingface.co/rednote-hilab/dots.ocr), [blog dots.ocr](https://github.com/rednote-hilab/dots.ocr/blob/master/assets/blog.md), [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct), [doc PP-OCRv5 multilang](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md), [tech report PaddleOCR 3.0 (arXiv 2507.05595)](https://arxiv.org/html/2507.05595v1), [benchmark Datalab](https://www.datalab.to/benchmark/overall), [Tesseract VN issue #66](https://github.com/tesseract-ocr/langdata/issues/66), [pbcquoc/vietocr](https://github.com/pbcquoc/vietocr).

**dots.ocr / dots.mocr.** License **MIT** ✅, format **safetensors** ✅, build trên Qwen2.5-VL, 3 B vừa 8–12 GB. **dots.ocr-1.5 đổi tên thành `dots.mocr` ngày 2026-03-19** với điểm cao hơn (OmniDocBench Elo 1059 vs 1027, olmOCR-bench 83.9 vs 79.1) — nếu bắt đầu từ đầu, dùng dots.mocr. Bench 100 ngôn ngữ không tách riêng tiếng Việt; tự đo trước khi quote số VN.

**Surya.** Sản phẩm flagship của Datalab nay là Chandra (proprietary). Surya vẫn open và hỗ trợ 90+ ngôn ngữ kể cả VN nhưng không còn là sản phẩm chủ lực.

**VietOCR (pbcquoc).** Không có commit nào nhìn thấy được trong 2025–2026. Ổn định nhưng dormant; không có giá trị thêm so với PP-OCRv5 hôm nay.

**PaddleOCR PP-OCRv5.** Format gốc là `inference.pdmodel` + `inference.pdiparams` — binary nhưng **không phải pickle** (qua được nguyên tắc 11). Paper fine-tune Hán-Nôm [arXiv 2510.04003](https://arxiv.org/html/2510.04003v1) (10/2025) cho thấy pipeline mở rộng được: **37.5 % → 50.0 %** trên Hán-Nôm chữ viết tay.

**6 tháng gần nhất.** **dots.ocr / dots.mocr** (07/2025 + 03/2026 đổi tên) — VLM-OCR open-weight mặc định mới; thắng Mistral OCR / Nougat / GOT-OCR trên OmniDocBench. **Qwen3-VL** (11/2025) — 19→32 ngôn ngữ hỗ trợ; VN giờ chính thức trong scope của một top open VLM. **Tech report PaddleOCR 3.0** đã củng cố câu chuyện multi-language. Datalab chuyển sang closed (Chandra). Bài báo academic đầu tiên về OCR Hán-Nôm cổ xuất hiện.

**Cạm bẫy VN.** **Stacked diacritic** (ố, ự, ặ) là nguồn lỗi #1 — Tesseract tệ nhất, PP-OCRv5 và VLM tốt hơn. Lớp nhầm lẫn ơ/ô, ư/u, đ/d ở DPI thấp — upsample scan lên ≥300 DPI. Mixed-script (VN + EN + số + Hán-Nôm) làm engine khoá ngôn ngữ trật; VLM xử lý tốt nhất. Bản in cũ / máy chữ / chữ viết tay — chỉ có VLM và PaddleOCR fine-tune chạy được.

---

## Pipeline khuyến nghị (tháng 4/2026)

| Lớp | **Fast** (CPU/4 GB) | **Mặc định** (GPU 8–12 GB) | **Accurate** (GPU 24 GB) |
|---|---|---|---|
| **LLM** | `sail/Sailor2-1B` (Apache, ~2 GB) — train VN, chạy CPU được | **`Qwen/Qwen3-8B`** (Apache, Q4 ~5 GB) | `sail/Sailor2-20B` Q4 (~12 GB) **hoặc** `Qwen3-32B` cho reasoning đơn ngôn ngữ |
| **Embedding** | `dangvantuan/vietnamese-embedding` (440 MB) **hoặc** `hiieu/halong_embedding` (MRR@10 **0.8799** Zalo Legal) | **`AITeamVN/Vietnamese_Embedding`** (BGE-M3 ft, **+27.9 % Acc@1** so với BGE-M3) | `intfloat/e5-mistral-7b-instruct` (VN-MTEB **67.67**, Pair **84.01**) |
| **OCR** | PaddleOCR PP-OCRv5 (Apache, <100 MB) | **`rednote-hilab/dots.mocr`** (MIT, 3 B, safetensors) — thắng Gemini-2.5-Pro trên OmniDocBench-EN | `Qwen/Qwen3-VL-8B-Instruct` (Apache, VN officially supported) — OCR + reasoning gộp |

### Hành động cụ thể cho nom-vn

1. **Đổi embedding:** đặt `AITeamVN/Vietnamese_Embedding` làm mặc định; giữ bản hiện tại làm `lite`. **Sửa claim "BGE-M3 #1 ở 64.90" trong `BENCHMARK.md`** — thực tế #1 là m-e5-large-instruct ở 67.99.
2. **Doc LLM:** thêm `sail/Sailor2-8B` dưới dạng "VN-tuned alternative" có tài liệu. Bỏ Vistral chờ license rõ.
3. **Viết lại OCR:** `BENCHMARK.md` hiện liệt kê VietOCR làm mặc định — cũ. Thay bằng tier PP-OCRv5 → dots.mocr → Qwen3-VL-8B.
4. **Nợ verified-numbers:** với cả dots.mocr và Qwen3-VL-8B chúng tôi đang dựa vào bằng chứng kế cận (multilingual). Theo nguyên tắc verified-benchmarks, trước khi publish dưới danh nghĩa VN-recommended, phải chạy bench best-of-N trên một corpus VN cam kết và ship script ở `benchmarks/`.
