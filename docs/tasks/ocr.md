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

## Post-correct với `vn-spell-correction-base` (opt-in)

Một thí nghiệm đã đo: chạy mô hình sửa chính tả trên output Tesseract
để cố gắng giảm CER. **Kết quả mixed** — gain WER ~5 pp tuyệt đối / 8 %
tương đối trên ảnh khó (CER ~30 %), gần wash trên ảnh sạch (Tesseract
< 1 % CER thì post-correct là no-op). Per-image: 11/30 ảnh được giúp,
12/30 bị hại trên ảnh khó.

| Variant | n | CER raw | CER post-correct | Δ CER | Δ WER |
|---|---:|---:|---:|---:|---:|
| `synthetic_ocr_vi/clean` | 20 | 0.00 % | 0.00 % | 0.00 | 0.00 |
| `synthetic_ocr_vi/noisy` | 20 | 0.70 % | 0.60 % | -0.10 | -0.38 |
| `synthetic_ocr_vi/hard` | 30 | 30.34 % | 29.91 % | -0.43 | **-5.22** |

Lý do gain nhỏ hơn literature (ByT5 fine-tune báo cáo 33-67 % giảm CER):
mô hình của ta train trên nhiễu synthetic kiểu typing, không phải lỗi
OCR-specific; tokenizer SentencePiece phân tách output Tesseract bị
corrupt thành garbage. Literature
([Tran et al. 2024](https://arxiv.org/html/2410.13305)) báo cáo
WER 27 % → 18 % khi train trực tiếp trên cặp `(Tesseract, GT)` —
nhưng giả định baseline ~5-30 % CER (printed scan).

### Negative result đã đo: handwriting (CER ~70 %) (2026-05-01)

Đã thử fine-tune `nrl-ai/vn-spell-correction-base` trên 9,626 cặp
`(Tesseract output, GT)` từ
[`brianhuster/VietnameseOCRdataset`](https://huggingface.co/datasets/brianhuster/VietnameseOCRdataset)
(Apache 2.0, handwriting). Bench trên 200 ảnh test split (giữ tách
khỏi training):

| Pipeline | CER | WER | helped/hurt |
|---|---:|---:|---|
| Tesseract `vie` baseline | **69.34 %** | 98.95 % | — |
| + base spell-correct (off-the-shelf) | 69.98 % (+0.64) | 98.56 % (-0.40) | 35 / 103 |
| + fine-tuned ocr-correct (3 epochs) | **81.80 % (+12.46)** | 101.26 % (+2.31) | 14 / 173 |

**Cả hai post-correct đều làm tệ hơn.** Fine-tuned phiên bản tệ
nhiều hơn — mô hình học bịa văn bản tiếng Việt plausible từ rác,
không sửa.

Ví dụ thất bại điển hình:
```
GOLD: khung cảnh kinh tế, xã hội và định chế.
RAW : vhuag cảnh kuÄ tố, xá đậu v3 đụnh chế   (CER 33 %)
PP  : và những cảnh sát, xã hội và 3            (CER 51 %)
```

Mô hình bịa "cảnh sát" thay vì "kinh tế".

**Root cause:** Tesseract `vie` không train cho VN handwriting; CER
70 % không đủ tín hiệu để recover. Đây là failure mode "hallucination
over-correction" mà
[Kanerva et al. 2025](https://arxiv.org/html/2502.01205v1) đã báo
cáo trên Finnish (LLM post-OCR -19 % đến -76 % CER, *tệ hơn* baseline).

**Bài học:** post-correct không cứu được OCR tệ. Đúng next step là
fix OCR engine (train TrOCR cho VN handwriting, hoặc dùng PaddleOCR
PP-OCRv5 với model handwriting), không phải fine-tune post-correct
trên data corrupt 70 %.

Reproduce (verify negative-result):

```bash
.venv/bin/python -m huggingface_hub.commands.huggingface_cli download \
    brianhuster/VietnameseOCRdataset dataset_small.zip --repo-type dataset \
    --local-dir /tmp/brianhuster_ocr
unzip /tmp/brianhuster_ocr/dataset_small.zip -d /tmp/brianhuster_ocr/

python training/ocr_correction/prep_data.py --engines tesseract,easyocr
TRAIN_HOST=mybox ./training/ocr_correction/launch_remote_train.sh
python benchmarks/accuracy/bench_ocr_post_correct_real.py \
    --corrector training/ocr_correction/checkpoints/vit5-ocr-correct/final \
    --json benchmarks/results/baseline_ocr_post_correct_real_finetuned.json
```

**Quyết định:** không bật mặc định (gain không đáng phức tạp), nhưng
làm sẵn như opt-in cho ai có ảnh quét xấu thực sự (CER ≥ 20 %).

```python
import pytesseract
from PIL import Image
from nom.text.diacritic_models import HFDiacriticModel

tess_text = pytesseract.image_to_string(Image.open("scan.png"), lang="vie")

# Opt-in post-correct (chậm thêm ~150 ms/dòng GPU, ~400 ms CPU)
corrector = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
clean = corrector(tess_text)
```

Reproduce:

```bash
python benchmarks/data/synthetic_ocr_vi/render_hard.py --n 30
python benchmarks/accuracy/bench_ocr_post_correct.py \
    --variants hard \
    --json benchmarks/results/baseline_ocr_post_correct_hard.json
```

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
