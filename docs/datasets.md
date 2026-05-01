# Bộ dữ liệu benchmark tiếng Việt

Catalogue của mọi corpus tiếng Việt ship cùng `nom-vn` để test và
benchmark. Mọi dataset đều license-clean cho **redistribution +
modification** (Apache 2.0 / CC-BY / CC-BY-SA / CC0 / public domain).
Mỗi thư mục có `LICENSE` và attribution per-file riêng.

> **Tìm dữ liệu _huấn luyện_ OCR?** Đó là audit riêng:
> [`research/ocr_training_data_vn_2026q2.md`](research/ocr_training_data_vn_2026q2.md)
> phân tích cái gì redistribute được, cái gì research-only và cái gì
> commercial, với ước tính chi phí cho synthetic generation, labeling
> và fine-tune PaddleOCR.

## Quick map

| Dataset | Modality | Register | Size | License | Đường dẫn |
|---|---|---|---|---|---|
| `diacritic_eval_v0` | text (câu) | hỗn hợp (4 register) | 55 câu | CC0 | [`benchmarks/data/diacritic_eval_v0.txt`](../benchmarks/data/diacritic_eval_v0.txt) |
| `udhr_vi` (text) | text (declarative) | hành chính/dịch | ~19 KB | CC-BY-SA 4.0 | [`benchmarks/data/udhr_vi/udhr_vi.txt`](../benchmarks/data/udhr_vi/) |
| `udhr_vi` (PDF) | PDF (text-layer) | hành chính | ~113 KB | public domain | [`benchmarks/data/udhr_vi/udhr_vie.pdf`](../benchmarks/data/udhr_vi/) |
| `wikisource_vi` | text (prose) | văn học cổ điển | ~14 KB qua 3 file | CC-BY-SA 4.0 (nội dung PD) | [`benchmarks/data/wikisource_vi/`](../benchmarks/data/wikisource_vi/) |
| `wiki_vi` | text (bài viết) | bách khoa toàn thư | 28 bài, ~1.16M ký tự | CC-BY-SA 4.0 | [`benchmarks/data/wiki_vi/articles.jsonl`](../benchmarks/data/wiki_vi/) |
| `tatoeba_vi` | text (câu) | hội thoại | 31.292 / 3.000 sample / 300 diacritic | CC-BY 2.0 FR | [`benchmarks/data/tatoeba_vi/`](../benchmarks/data/tatoeba_vi/) |
| `udhr_vi` (diacritic 72) | text (câu) | hành chính/pháp lý | 72 câu | public domain | [`benchmarks/data/udhr_vi/diacritic_eval_udhr.txt`](../benchmarks/data/udhr_vi/) |
| `synthetic_ocr_vi` | ảnh PNG | mục tiêu OCR | 40 ảnh (clean+noisy) | CC0 | [`benchmarks/data/synthetic_ocr_vi/`](../benchmarks/data/synthetic_ocr_vi/) |
| `flores_vi` | text (parallel) | tin tức / hỗn hợp | gated, không commit | CC-BY-SA 4.0 | [`benchmarks/data/flores_vi/`](../benchmarks/data/flores_vi/) |
| `ud_vi_vtb` | CoNLL-U (gold word-segmented) | văn học | 800 test / 1.123 dev / 1.400 train câu; 11.692 token gold test | CC-BY-SA-4.0 | [`benchmarks/data/ud_vi_vtb/`](../benchmarks/data/ud_vi_vtb/) |
| `spell_correction_eval` | text (cặp noisy/clean, synthetic) | 4 register × 2 noise levels | 2.098 cặp | CC0 | [`benchmarks/data/spell_correction_eval/`](../benchmarks/data/spell_correction_eval/) |
| `spell_correction_eval_real` | text (cặp noisy/clean, **OOD hand-curated**) | 6 register thực tế (forum / mobile / telex thật / OCR engine / pháp lý / tin tức) | 150 câu | CC0 | [`benchmarks/data/spell_correction_eval_real/`](../benchmarks/data/spell_correction_eval_real/) |

Tổng dung lượng commit: **~2.8 MB**.

## Mỗi dataset hợp với cái gì

| Module | Dataset khuyến nghị | Lý do |
|---|---|---|
| `nom.text` (normalize, fix_diacritics) | `diacritic_eval_v0`, `udhr_vi/diacritic_eval_udhr.txt`, `tatoeba_vi/diacritic_eval_300.txt`, `ud_vi_vtb/test.conllu` | Ma trận 4 register (hành chính / kinh doanh / hội thoại / văn học) |
| `nom.text.fix_diacritics` (sửa chính tả) | `spell_correction_eval` (synthetic, in-distribution) + `spell_correction_eval_real` (hand-curated, OOD) | Synthetic đo trường-hợp-bộ-sinh-nhiễu; OOD đo nhiễu thực tế (sample size nhỏ, kèm bootstrap CI) |
| `nom.text.word_tokenize` | `ud_vi_vtb` (split test) | Word-segmentation P/R/F1 gold so với underthesea |
| `nom.chunking` | `wiki_vi`, `wikisource_vi`, `udhr_vi` | Prose dài có cấu trúc đoạn |
| `nom.embeddings` | `tatoeba_vi`, `flores_vi` (khi có) | Cặp đánh giá ở mức câu |
| `nom.retrieve` (BM25, dense, hybrid) | corpus `wiki_vi` + query handcrafted | Topic bách khoa đa dạng cho IR |
| `nom.rag` | `wiki_vi` (corpus) + `tatoeba_vi` (query) | Retrieval + generation end-to-end |
| `nom.doc` (trích xuất text từ PDF) | `udhr_vi/udhr_vie.pdf` | Baseline PDF born-digital |
| `nom.doc` (OCR trên ảnh) | `synthetic_ocr_vi` (clean + noisy) | Nhãn thật chuẩn xác, an toàn cho regression |

## Đã publish trên Hugging Face Hub

Hai dataset chúng tôi gom lại cho khôi phục dấu được mirror trên HF Hub
để dùng `datasets.load_dataset` mà không cần clone repo:

| Dataset HF | License | Splits / configs | Bên trong |
|---|---|---|---|
| [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) | CC-BY-SA-4.0 (chặt nhất trong các thành phần) | `business_55`, `formal_72`, `conversational_300`, `literary_800` | Lưới đánh giá 4 register (1.227 cặp câu) dùng để bench mọi mô hình diacritic trong repo. License per-config ghi rõ trong card. |
| [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) | CC-BY-SA-4.0 (per-config: wiki=CC-BY-SA-4.0, news=CC-BY-4.0) | `wiki_500k`, `news_150k` | 500K cặp Wikipedia + 150K cặp tin tức VN đã sửa NFC. Đã chống rò eval với `vn-diacritic-eval`. NFC-normalize tại lúc ghi. |

Loading:

```python
from datasets import load_dataset

# Eval set — bench bất kỳ mô hình nào trên cùng lưới
ds = load_dataset("nrl-ai/vn-diacritic-eval", "business_55", split="train")

# Cặp huấn luyện — mix Wikipedia + news đã build sẵn
wiki = load_dataset("nrl-ai/vn-diacritic-train", "wiki_500k", split="train")
news = load_dataset("nrl-ai/vn-diacritic-train", "news_150k", split="train")
```

Bản local dưới `benchmarks/data/` và `training/diacritic/data/` giống
hệt từng bit với bản HF; entry point nào cũng hoạt động.

## Tái lập corpus từ một bản clone sạch

```bash
# Text + PDF — đều idempotent
python benchmarks/data/_fetch_all.py

# Eval slice diacritic (300 hội thoại, 72 hành chính/pháp lý)
python benchmarks/data/tatoeba_vi/build_diacritic_eval.py
python benchmarks/data/udhr_vi/build_diacritic_eval.py

# Ảnh OCR synthetic — tất định qua RNG seeded
python benchmarks/data/synthetic_ocr_vi/render.py
```

Fetcher chỉ dùng stdlib (`urllib.request`) cộng `huggingface_hub` cho
dataset gated. Renderer cần `Pillow` và font hệ thống có hỗ trợ tiếng
Việt (DejaVu / Lato / FreeFont — có sẵn trên đa số distro Linux).

## Lập trường license (chính sách no-pickle + verified-benchmarks của chúng tôi)

- **LICENSE per-folder** với quy tắc attribution rõ ràng — không bao
  giờ dựa vào việc kế thừa "license file" toàn cục.
- **Không pickle, không binary opaque** trong bất kỳ dataset commit
  nào. PNG và PDF là format mở; mọi thứ còn lại là plaintext hoặc TSV.
- **Tái lập được từ script** — mọi dataset commit đều regenerate được
  từ `_fetch_all.py` hoặc `render.py`. Không có artifact black-box.
- **Caveat "share-alike" của CC-BY-SA**: tác phẩm phái sinh tích hợp
  dataset CC-BY-SA kế thừa nghĩa vụ share-alike. Mã thư viện
  (Apache 2.0) không bị — chỉ đầu ra nướng kèm *nội dung* CC-BY-SA bị.

## Nguồn đã cân nhắc và loại bỏ

| Nguồn | Lý do loại |
|---|---|
| Corpus shared-task VLSP | License research-only, không redistribute |
| VnExpress / Tuổi Trẻ / scrape tin tức | Có copyright, không có giấy phép permissive |
| CC-100 / mC4 / CulturaX | License không rõ (Common Crawl ToS mơ hồ) |
| Medical-QA của VietAI | Research-only |
| Tài liệu scan của Vinacademy / VinAI | License không rõ |

## Sẽ thêm sau

- **Ảnh biển hiệu VN trên Wikimedia Commons** — ảnh OCR thực tế, CC-BY-SA / PD per-file
- **Sách VN scan của Internet Archive** — pre-1928 PD theo luật Mỹ, fetch qua `download.sh`
- **Văn bản pháp lý vbpl.vn** — PD theo luật Việt Nam (Luật SHTT 2005, Điều 15)
