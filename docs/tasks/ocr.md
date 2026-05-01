# OCR tiếng Việt

Trích văn bản từ ảnh hoặc PDF scan. Mặc định của chúng tôi là
**Tesseract 5 + traineddata `vie`** — đo nhanh hơn, chính xác hơn các
ứng viên VLM cho dòng chữ in sạch. Khi tài liệu là PDF born-digital
(layer text), dùng [`pdf-extraction`](/tasks/pdf-extraction) thay vì.

## TL;DR — gợi ý của chúng tôi

```bash
# Hệ thống — install Tesseract 5 + ngôn ngữ vie
sudo apt install tesseract-ocr tesseract-ocr-vie  # Ubuntu / Debian
brew install tesseract tesseract-lang             # macOS
conda install -c conda-forge tesseract            # cross-platform
```

```python
from nom.doc.ocr import TesseractOCR

ocr = TesseractOCR(lang="vie")
text = ocr.read("scan.png")  # hoặc bytes / PIL Image
```

**Quy tắc:**

- *Dòng chữ in sạch trên ảnh quét chất lượng tốt* → Tesseract `vie`.
  CER ~5.5 %, p50 80 ms / dòng.
- *Tài liệu / form / ID card / layout phức tạp* → VLM (Qwen2.5VL,
  Gemma3-Vision) — nhưng chỉ ở mức tài liệu, không ở mức dòng (xem
  cảnh báo bên dưới).
- *PDF có text layer* → `nom.doc.pdf` qua pypdfium2 (không OCR).

## Bức tranh công khai

| Backend | License | CER trên `synthetic_ocr_vi` | Latency p50 |
|---|---|---:|---:|
| **Tesseract 5 + `vie`** ⭐ | Apache 2.0 | **5.53 %** | 80 ms |
| EasyOCR | Apache 2.0 | 9.39 % | 250 ms |
| `qwen2.5vl:7b` | Apache 2.0 (model) | 31.07 % | 1.4 s |
| Surya OCR | open-RAIL-M | — | — |

**VLM hallucination cảnh báo**: trên crop dòng đơn (typical OCR setup),
Qwen2.5VL 7B đạt **31 % CER** — gấp 6 lần Tesseract. Lý do: prior ngôn
ngữ chi phối khi tín hiệu thị giác hẹp. VLM là công cụ đúng cho **hiểu
tài liệu** (form, hoá đơn, ID card, chữ viết tay) chứ không phải dòng
chữ in sạch.

`Surya OCR` fail audit license: code GPL-3 + model open-RAIL-M không
tương thích với mục tiêu phân phối Apache 2.0 của chúng tôi. Chúng tôi
**không ship** Surya — bỏ qua dù số quality cạnh tranh.

## Pipeline của chúng tôi

```python
from nom.doc.ocr import TesseractOCR
from PIL import Image

ocr = TesseractOCR(lang="vie", config="--psm 6")  # PSM 6 = single uniform block
text = ocr.read(Image.open("scan.png"))
```

Adapter wrap `pytesseract` với:

- Pre-process tự động (deskew nhẹ, contrast normalize) khi `auto_preprocess=True`
- NFC chuẩn hoá output
- Rule fallback nếu Tesseract không trả về gì cho dòng (ảnh trắng / quá nhỏ)

## Kết quả — đã đo

Đo trên `benchmarks/data/synthetic_ocr_vi/` (40 ảnh PNG, ground truth chuẩn xác,
clean + noisy mix). Metric: CER (character error rate) tính trên chuỗi
ký tự đã NFC. Diacritic-CER tính riêng cho combining marks (xem
[docs/benchmark.md](/benchmark)).

| Backend | CER | Diacritic-CER | Latency p50 |
|---|---:|---:|---:|
| Tesseract 5 + `vie` | **5.53 %** | 8.21 % | 80 ms |
| EasyOCR | 9.39 % | 14.88 % | 250 ms |
| qwen2.5vl:7b VLM | 31.07 % | 38.45 % | 1.4 s |

JSON baseline: `benchmarks/results/baseline_ocr_*.json`.

## Mô hình `nrl-ai/*` đã huấn luyện

Hiện chưa có. Chúng tôi đã audit nhiều phương án custom OCR:

- **Train từ đầu** một CRNN VN-only — chi phí cao (~2 ngày GPU trên
  ImageNet-VN synthetic), kết quả khó vượt Tesseract trên dòng in sạch.
- **Fine-tune `microsoft/trocr-small-printed`** — khả thi với ~6 h GPU
  trên synthetic VN, có khả năng thu hẹp khoảng cách Tesseract trên một
  số corner case (bold / italic / vintage form).
- **Fine-tune cho chữ viết tay tiếng Việt** — chỗ trống thật của hệ
  sinh thái; nhưng cần dataset chữ viết tay VN curate được — đó là
  một dự án riêng.

Quyết định hiện tại: **không train custom OCR**. Tesseract đã rất tốt
cho dòng in sạch; chữ viết tay là sprint riêng cần dataset.

## Tái lập

```bash
# Sinh ảnh test (deterministic, không cần mạng)
python benchmarks/data/synthetic_ocr_vi/render.py

# Bench
python benchmarks/accuracy/bench_ocr.py \
    --backend tesseract \
    --json benchmarks/results/baseline_ocr_tesseract.json
```

## Tham khảo

- Tesseract 5: <https://github.com/tesseract-ocr/tesseract>
- `vie` traineddata (best): <https://github.com/tesseract-ocr/tessdata_best>
- EasyOCR: <https://github.com/JaidedAI/EasyOCR>
- TrOCR (Microsoft): <https://huggingface.co/microsoft/trocr-base-printed>
