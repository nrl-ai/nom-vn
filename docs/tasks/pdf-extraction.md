# Trích văn bản từ PDF

PDF born-digital có **text layer** (chuỗi ký tự thực sự nhúng trong
file) — không cần OCR. Trích được nó ra với accuracy gần 100 % và
throughput cao gấp hàng nghìn lần so với chạy OCR. Cho PDF scan
(bitmap-only), xem [`/tasks/ocr`](/tasks/ocr).

## TL;DR — gợi ý của chúng tôi

```bash
pip install nom-vn  # pypdfium2 đi sẵn
```

```python
from nom.doc.pdf import extract_text

text = extract_text("contract.pdf")
# Mọi trang concat, NFC-chuẩn-hoá, đoạn được giữ nguyên
```

**pypdfium2** (BSD-3 wrap của Google PDFium Apache-2.0) — wrapper
license-clean của thư viện PDF chính thức trong Chrome. Char overlap
99.81 % trên `udhr_vi.pdf`, 2.35 M chars/s — nhanh hơn `pdfplumber`
46×, nhanh hơn Docling 156×.

## Bức tranh công khai

| Backend | License | Char overlap (udhr_vi.pdf) | Throughput | Kết luận |
|---|---|---:|---:|---|
| **pypdfium2** ⭐ | BSD-3 (Apache 2.0 PDFium underneath) | **99.81 %** | **2.35 M chars/s** | mặc định ship trong nom |
| `pdfplumber` | MIT | 99.62 % | 51 k chars/s | đầy đủ, có support layout phức tạp; chậm 46× |
| Docling | MIT | 95.10 % | 15 k chars/s | nặng (kéo torch), chậm 156× |
| PyMuPDF | **AGPL-3** | 99.78 % | 1.82 M chars/s | kéo cả downstream thành AGPL — **bỏ qua** |
| Tika | Apache 2.0 | — | — | server-based, không phù hợp với pipeline Python |

**License cảnh báo:** PyMuPDF nhanh và chính xác nhưng giấy phép AGPL-3
**bắt mọi project sử dụng cũng phải AGPL**. Cho thư viện Apache 2.0 muốn
distribute commercial-friendly, PyMuPDF là một no-go.

## Pipeline của chúng tôi

```python
from nom.doc.pdf import extract_text, extract_pages

# Toàn bộ tài liệu
text = extract_text("contract.pdf")

# Per page — cho RAG indexing
for page_no, page_text in extract_pages("contract.pdf"):
    print(f"--- Page {page_no} ---")
    print(page_text[:200])
```

Adapter:

- NFC chuẩn hoá output
- Loại bỏ ký tự non-printable / page-break giả
- Tự fall back sang OCR (`/tasks/ocr`) nếu page có < N ký tự
  text-layer (page bitmap pure)

## Kết quả — đã đo

Đo trên `benchmarks/data/udhr_vi/udhr_vie.pdf` (born-digital, 6 trang,
~19 K ký tự) — ground truth là `udhr_vi.txt` parallel.

| Backend | Char overlap | Throughput | Best-of-3 latency |
|---|---:|---:|---:|
| pypdfium2 | **99.81 %** | 2.35 M chars/s | 8.0 ms |
| pdfplumber | 99.62 % | 51 k chars/s | 367 ms |
| PyMuPDF | 99.78 % | 1.82 M chars/s | 10.4 ms |
| Docling | 95.10 % | 15 k chars/s | 1.27 s |

JSON baseline: `benchmarks/results/baseline_pdf_*.json`.

## Tái lập

```bash
python benchmarks/perf/bench_pdf_extract.py
```

## Tham khảo

- PDFium project (Google): <https://pdfium.googlesource.com/pdfium/>
- pypdfium2: <https://pypi.org/project/pypdfium2/>
- pdfplumber: <https://github.com/jsvine/pdfplumber>
