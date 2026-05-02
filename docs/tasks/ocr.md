# OCR tiếng Việt

Trích văn bản từ ảnh hoặc PDF scan. Mặc định của chúng tôi là
**Tesseract 5 + traineddata `vie`** — đo nhanh hơn, chính xác hơn các
ứng viên VLM cho dòng chữ in sạch. Khi tài liệu là PDF born-digital
(layer text), dùng [`pdf-extraction`](/tasks/pdf-extraction) thay vì.

## TL;DR — chọn engine theo loại dữ liệu (đo 2026-05-01)

Đo trên 200 ảnh handwriting (`brianhuster/VietnameseOCRdataset`) +
70 ảnh printed (`benchmarks/data/synthetic_ocr_vi/{clean,noisy,hard}`).

| Loại dữ liệu | Engine khuyến nghị | CER đã đo | Latency | Khi nào chọn engine khác |
|---|---|---:|---:|---|
| 🖨️ **Văn bản in sạch** (giấy A4 quét sắc nét, font chuẩn) | **Tesseract `vie`** | **0.00 %** | 80 ms | (không có lý do — Tesseract trên printed clean là gần như hoàn hảo) |
| 🖨️ **Văn bản in nhiễu nhẹ** (quét hơi mờ, blur 1-2px) | **Tesseract `vie`** | **0.70 %** | 80 ms | dùng VietOCR nếu cần beam-search; PaddleOCR và RapidOCR cùng dùng `latin_PP-OCRv5_mobile_rec` không phục hồi được dấu thanh |
| 🖨️ **Scan kém chất lượng** (giấy cũ, mực phai, JPEG nén) | **VietOCR** (nhỉnh hơn) | **29.00 %** | 246 ms | Tesseract là lựa chọn dự phòng nếu cần latency thấp |
| ✍️ **Chữ viết tay** (cá nhân, học sinh, ghi chép) | **VietOCR** | **31.82 %** | 246 ms | PaddleOCR đứng thứ 3 (59.4 %); kém VietOCR ~28 pp + thiếu recognizer VN-specific |
| 📋 **Form / hoá đơn / ID có layout** | **VLM** (Qwen2.5VL, Gemma3-Vision) | chưa có corpus công khai phù hợp | 1.4-2 s | Tesseract / VietOCR cho các trường text thuần khi đã trích được crop. Cần curate corpus form VN có ground-truth trước khi đo được. |
| 📷 **Ảnh điện thoại nhiễu mạnh** (perspective, lighting) | **VLM** ở mức tài liệu hoặc preprocess + VietOCR | chưa có corpus công khai phù hợp | 1.4-2 s | Cần curate corpus phone-OCR VN có GT (MC-OCR 2021 chưa rõ license). VLM vẫn là khuyến nghị mặc định cho lớp này. |
| 📜 **Sách cổ / vintage** (1850-2000) | TBD — chưa đo | — | — | Future work; VieBookRead corpus license afl-3.0, chưa đưa vào harness. |
| 📄 **PDF born-digital có text-layer** | **`nom.doc.pdf`** (pypdfium2) | 99.81 % char overlap | < 1 ms | không phải OCR |

```bash
# Tesseract cho printed clean / noisy
sudo apt install tesseract-ocr tesseract-ocr-vie

# VietOCR cho handwriting (cần install từ source — PyPI bị broken)
pip install git+https://github.com/pbcquoc/vietocr.git
```

```python
# Printed text — Tesseract (nhanh, chính xác trên chữ in sạch)
from nom.doc.ocr import TesseractOCR
ocr = TesseractOCR(lang="vie")
text = ocr.read("scan.png")

# Handwriting — VietOCR (transformer VN-specific, Apache 2.0)
from vietocr.tool.config import Cfg
from vietocr.tool.predictor import Predictor
from PIL import Image
cfg = Cfg.load_config_from_name("vgg_transformer")
cfg["device"] = "cuda"
predictor = Predictor(cfg)
text = predictor.predict(Image.open("handwriting_line.png").convert("RGB"))
```

**Quy tắc:**

- *Chữ in sạch / quét tốt* → Tesseract `vie`. 0-1 % CER, 80 ms/dòng.
- *Chữ viết tay tiếng Việt* → **VietOCR** vgg_transformer. 32 % CER trên
  brianhuster handwriting (so với Tesseract 69 %; **cải thiện 37.5 pp
  tuyệt đối, ~54 % tương đối**).
- *Tài liệu / form / ID card / layout phức tạp* → VLM (Qwen2.5VL,
  Gemma3-Vision) — nhưng chỉ ở mức tài liệu, không ở mức dòng (xem
  cảnh báo bên dưới).
- *PDF có text layer* → `nom.doc.pdf` qua pypdfium2 (không OCR).

## Bức tranh công khai (đầy đủ, đo 2026-05-01)

| Backend | License | CER `printed clean` | CER `printed noisy` | CER `printed hard` | CER `handwriting` | Latency p50 |
|---|---|---:|---:|---:|---:|---:|
| **Tesseract 5 + `vie`** | Apache 2.0 | **0.00 %** ⭐ | **0.70 %** ⭐ | 30.34 % | 69.34 % | 80 ms |
| **VietOCR vgg_transformer** | Apache 2.0 | 1.41 % | 3.37 % | **29.00 %** ⭐ | **31.82 %** ⭐ | 240 ms |
| EasyOCR | Apache 2.0 | 1.42 % | 4.87 % | 87.09 % | 71.52 % | 35-60 ms |
| PaddleOCR PP-OCRv5 (latin_mobile_rec) | Apache 2.0 | 24.70 % | 31.33 % | 86.13 % | 59.43 % | 1170-1260 ms |
| RapidOCR (ONNX, PaddleOCR port) | Apache 2.0 | 63.97 % | 77.83 % | 100.00 % | 97.20 % | 130-250 ms |
| TrOCR base-handwritten (English-only baseline) | MIT | 32.89 % | 38.07 % | 93.76 % | 75.89 % | 180-280 ms |
| `qwen2.5vl:7b` (VLM) | Apache 2.0 (model) | 31.07 % | not benched (no Ollama VLM cached on bench host) | not benched | not benched | 1.4 s |
| Surya OCR | open-RAIL-M | not benched (license fails audit) | — | — | — | — |

**Phát hiện quan trọng 2026-05-01:**

- **VietOCR là engine đúng cho chữ viết tay tiếng Việt.** -37.5 pp
  CER tuyệt đối so với Tesseract (69.34 → 31.82 %), -54 % tương đối.
- **Tesseract vẫn là lựa chọn đúng cho văn bản in sạch.** 0.00 %
  CER trên synthetic printed clean. VietOCR đạt 1.41 % — không đáng
  để đánh đổi tốc độ (Tesseract nhanh hơn 3 lần).
- **PaddleOCR PP-OCRv5 đứng thứ 3-4 trên *mọi* register tiếng Việt** —
  re-test 2026-05-01 sau khi thử default pipeline, doc-prep skipped,
  standalone `TextRecognition`, và `latin_PP-OCRv5_server_rec`; re-grid
  full landscape 2026-05-02. Lý do cấu trúc: **PP-OCRv5 không ship
  recognizer VN-specific**; `lang='vi'` chỉ load
  `latin_PP-OCRv5_mobile_rec` — model Latin script generic nhận diện
  được bảng chữ cái nhưng strip dấu thanh (acute / grave / hook /
  tilde / dot below) ở mức cao trên cả printed clean (24.70 % CER vs
  Tesseract 0.00 %).
- **RapidOCR là port ONNX của PaddleOCR — cùng failure mode.**
  Docling default `ocr_engine='rapidocr'` cũng kém viable cho tiếng
  Việt. Trên printed clean nó còn drop dấu (63.97 % CER); trên
  handwriting line crop chi nhận diện gần như zero (97.20 % CER).
- **Surya OCR fail audit license** (model open-RAIL-M không tương
  thích Apache 2.0 toolkit). Bỏ qua kể cả khi quality cạnh tranh.

JSON nguồn:
[`baseline_ocr_engines.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_ocr_engines.json)
(handwriting, n=200) ·
[`baseline_ocr_engines_printed.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_ocr_engines_printed.json)
(printed clean / noisy / hard, full grid) ·
[`baseline_ocr_engines_per_register.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_ocr_engines_per_register.json)
(per-register summary).

Tái lập:

```bash
# Handwriting register
python benchmarks/accuracy/bench_ocr_engines.py \
    --json benchmarks/results/baseline_ocr_engines.json
# Printed registers (clean / noisy / hard)
python benchmarks/accuracy/bench_ocr_engines_printed.py \
    --json benchmarks/results/baseline_ocr_engines_printed.json
```

## Pipeline thực dụng theo loại dữ liệu

### Pattern 1: Văn bản in tiếng Việt (default)

```python
from nom.doc.ocr import TesseractOCR

ocr = TesseractOCR(lang="vie")
text = ocr.read("scan.png")
# 0-1 % CER, ~80 ms/ảnh
```

Dùng cho scan tài liệu chính phủ, hợp đồng in, sách giáo khoa, tin
tức scan. Tesseract trên printed clean gần như hoàn hảo — không có
alternative đáng cân nhắc.

### Pattern 2: Chữ viết tay tiếng Việt

```bash
pip install git+https://github.com/pbcquoc/vietocr.git  # PyPI bị broken
```

```python
from PIL import Image
from vietocr.tool.config import Cfg
from vietocr.tool.predictor import Predictor

cfg = Cfg.load_config_from_name("vgg_transformer")
cfg["device"] = "cuda"
cfg["predictor"]["beamsearch"] = False
predictor = Predictor(cfg)

text = predictor.predict(Image.open("note.png").convert("RGB"))
# 32 % CER, ~246 ms/dòng GPU
```

Dùng cho ghi chép cá nhân, biểu mẫu điền tay, vở học sinh, ghi
chú trên tài liệu. **VietOCR thắng tuyệt đối** — không có engine
nào trong landscape gần ngang. PaddleOCR PP-OCRv5 đứng thứ 3 ở
59.4 % CER (gấp ~1.9 lần lỗi của VietOCR + chậm 5 lần). RapidOCR
gần như fail toàn bộ (97 % CER) — detector không bắt được dòng
chữ viết tay.

### Pattern 3: Form / hoá đơn / ID card / layout phức tạp

```python
from nom.llm import Ollama
import base64, io
from PIL import Image

img = Image.open("invoice.png")
buf = io.BytesIO()
img.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode()

llm = Ollama(model="qwen2.5vl:7b", think=False)
out = llm.complete(
    "Trích các trường: tên, ngày, số tiền. Trả về JSON.",
    images=[b64],
)
```

Dùng VLM khi tài liệu có cấu trúc + cần hiểu ngữ cảnh. VLM nhìn toàn
bộ ảnh, hiểu form layout. **Cảnh báo:** không dùng VLM cho dòng đơn
crop — VLM hallucinate trên dòng đơn (xem cảnh báo bên dưới).

### Pattern 4: PDF born-digital có text-layer

```python
from nom.doc.pdf import extract_text
text = extract_text("contract.pdf")
# 99.81 % char overlap, 2.35 M chars/s, không phải OCR
```

**Không bao giờ chạy OCR trên born-digital PDF** — text đã có sẵn.
Xem [`/tasks/pdf-extraction`](/tasks/pdf-extraction).

### Pattern 5: Hybrid auto-routing

Cho ứng dụng có ảnh hỗn hợp register chưa biết:

```python
import pytesseract
from PIL import Image

def smart_ocr(img_path: str) -> str:
    img = Image.open(img_path)
    # Try Tesseract first — fast, high-quality on printed
    data = pytesseract.image_to_data(
        img, lang="vie", output_type=pytesseract.Output.DICT
    )
    confs = [int(c) for c in data["conf"] if c.lstrip("-").isdigit() and int(c) > 0]
    avg = sum(confs) / max(1, len(confs))

    if avg >= 70:  # printed clean — Tesseract is confident
        return pytesseract.image_to_string(img, lang="vie")

    # Low Tesseract confidence — escalate to VietOCR (handwriting / hard scan)
    from vietocr.tool.config import Cfg
    from vietocr.tool.predictor import Predictor
    cfg = Cfg.load_config_from_name("vgg_transformer")
    cfg["device"] = "cuda"
    return Predictor(cfg).predict(img.convert("RGB"))
```

Tự động chọn engine dựa trên Tesseract confidence: printed sạch chạy
fast path, handwriting fallback sang VietOCR.

## VLM hallucination cảnh báo

Trên crop dòng đơn (typical OCR setup), Qwen2.5VL 7B đạt **31 % CER**
— gấp 6 lần Tesseract trên printed clean. Lý do: prior ngôn ngữ
chi phối khi tín hiệu thị giác hẹp. VLM là công cụ đúng cho **hiểu
tài liệu** (form, hoá đơn, ID card, chữ viết tay nguyên trang) chứ
không phải dòng chữ in sạch crop.

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

### Phân tích sâu thất bại — vì sao post-correct không cứu được handwriting (2026-05-01)

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

#### Quantified failure modes (analyze_failure.py)

Diagnostic script `training/ocr_correction/analyze_failure.py` đã phân
tích 200 ảnh test:

| Chỉ báo | Off-the-shelf base | Fine-tuned ocr-correct |
|---|---:|---:|
| **% từ trong post-correct KHÔNG có trong raw OCR** (chỉ số hallucination) | 39.5 % | **91.3 %** |
| Độ dài trung bình output (ký tự, gold = 67) | 46.4 | 39.3 |
| Số output trùng lặp (mode collapse) | 0 | 2 (`. `, ...) |
| Per-bucket Δ CER (50-70 % CER bucket, n=105) | +1.45 pp | **+15.58 pp** |
| Per-bucket Δ CER (70 %+ bucket, n=88) | -0.66 pp | **+7.70 pp** |

**91 % các từ trong output fine-tune không tồn tại trong input gốc**
— mô hình đang sinh tự do thay vì sửa.

#### Inference-time guards giảm regression nhưng không cứu được

Thử thêm guardrails (beam search 4, no-repeat n-gram=3, length-conditioned
generation, confidence gate dựa trên ký tự diacritic VN):

| Pipeline | CER | WER | Δ vs raw |
|---|---:|---:|---:|
| Tesseract raw only | 69.34 % | 98.95 % | baseline |
| + spell-correction-base (greedy) | 69.98 % | 98.56 % | +0.64 / -0.40 |
| + spell-correction-base (guarded) | 70.40 % | 99.19 % | +1.06 / +0.24 |
| + fine-tuned ocr-correct (greedy) | 81.80 % | 101.26 % | +12.46 / +2.31 |
| + fine-tuned ocr-correct (guarded) | 78.32 % | 98.91 % | **+8.98** / **-0.04** |

Guards giảm regression của fine-tune từ +12.46 → +8.98 pp CER (cải thiện
3.5 pp) nhưng không đảo ngược được kết luận: **post-correct trên
Tesseract handwriting không thể net-positive**.

#### Root cause

**OCR baseline 70 % CER là quá xấu để post-correct cứu được.** Khi
7/10 ký tự sai, không còn đủ tín hiệu cho mô hình recover nội dung
gốc. Kết quả tốt nhất là "không làm gì" (raw_only) — bất kỳ post-correct
nào đều thêm risk hallucination.

Literature tham khảo:

- [Tran et al. 2024](https://arxiv.org/html/2410.13305) báo cáo
  WER 27 % → 18 % khi train trực tiếp trên cặp `(Tesseract, GT)` —
  nhưng baseline của họ là **printed scan ~30 % CER**, không phải
  handwriting 70 %.
- [Kanerva et al. 2025](https://arxiv.org/html/2502.01205v1) báo cáo
  LLM post-OCR trên Finnish: CER -19 % đến -76 % (tệ hơn baseline)
  trên một số corpus — chính xác failure mode chúng tôi gặp.

### Docling và toolchain ngoài — không có shortcut VN-specific

[Docling](https://github.com/DS4SD/docling) (IBM Research) là document
conversion toolkit phổ biến nhất 2026, nhưng **không ship recognizer
OCR riêng**: nó delegate qua plug-in cho EasyOCR (default), Tesseract
(`ocr_engine='tesseract'`), hoặc RapidOCR (`ocr_engine='rapidocr'`).
Cả ba đều đã có trong bảng landscape ở trên — không có engine "ẩn"
nào để khai thác. Docling thêm giá trị ở **layout** (RT-DETR) và
**bảng** (TableFormer), không phải OCR. Cho VN handwriting, dùng
VietOCR trực tiếp; cho VN printed cấu trúc (báo cáo, bảng), Docling +
Tesseract `vie` là tổ hợp đúng.

### Test corpora bổ sung — chưa benched

Ngoài `brianhuster/VietnameseOCRdataset` (handwriting, đang dùng) +
`benchmarks/data/synthetic_ocr_vi/` (printed in-tree generator),
các corpus công khai tiếng Việt khác có thể bổ sung:

| Corpus | License | Register | Quy mô | Trạng thái |
|---|---|---|---|---|
| [`brianhuster/VietnameseOCRdataset`](https://huggingface.co/datasets/brianhuster/VietnameseOCRdataset) | Apache 2.0 | Handwriting line crops | 7,296 ảnh | ✅ Đang dùng (test split, n=200) |
| [`iAmHieu2012/vietnamese-ocr-dataset-aggregated`](https://huggingface.co/datasets/iAmHieu2012/vietnamese-ocr-dataset-aggregated) | MIT | Printed page scans | ~3,500 trang | 📋 Future test bed (cấp page, cần line-detect trước) |
| `VieBookRead` | afl-3.0 | Sách scan (1850-2000) | TBD | 📋 Cho register vintage |
| `MC-OCR 2021` | Cần xác thực | Receipts / hoá đơn | TBD | 📋 License chưa rõ — verify trước khi dùng |
| `manhha2502/Vietnamese_Handwriting_OCR` | Cần xác thực | Handwriting | TBD | 📋 License chưa rõ |

`benchmarks/data/synthetic_ocr_vi/` vẫn là source-of-truth deterministic
cho printed (sinh tại chỗ, CC0). `iAmHieu2012/...` là MIT real scan,
là test bed thật cho printed register khi cần đánh giá độ generalization
ngoài synthetic.

### Future work — đường đi để OCR thật sự cải thiện

Xếp theo ROI giảm dần:

1. **Replace OCR engine với một mô hình handwriting-aware**
   (không phải post-correct). ✅ Đã chọn VietOCR cho handwriting; phần
   còn lại là tinh chỉnh.
   - **VietOCR transformer** (cộng đồng pbcquoc/vietocr): VN-specific,
     license Apache 2.0, format `.pth` (PyTorch state dict). **Đang là
     default** cho register handwriting (31.82 % CER vs Tesseract
     69.34 %).
   - ~~**PaddleOCR PP-OCRv5** với VN handwriting model~~ — re-test
     2026-05-01 xác nhận PP-OCRv5 không ship recognizer VN-specific;
     `lang='vi'` chỉ dùng `latin_PP-OCRv5_mobile_rec`. CER 59.43 %
     trên handwriting (thứ 3, kém VietOCR ~28 pp). Không phải con đường.
   - **TrOCR fine-tune trên brianhuster** (start from
     `microsoft/trocr-base-handwritten`, replace tokenizer với
     BARTpho-syllable, train ~8 h GPU). Có thể đẩy CER xuống dưới
     20 % nếu pipeline tokenizer + augmentation chuẩn.
2. **Gate post-correct với confidence proxy** — chỉ áp dụng khi raw
   OCR đạt baseline 5-30 % CER (printed text). Đã có hint từ
   `_confidence_gate_passes()` trong `bench_with_guards.py` —
   chỉ cần thêm một phán đoán "raw đủ tốt để correct" để skip cases
   gibberish.
3. **Train OCR-correction trên printed-VN corpus thay vì handwriting**
   — generate cặp `(Tesseract output trên ảnh print synthetic, GT)`
   với CER 5-15 %. Đây là band post-correct hoạt động được.
4. **Switch base sang ByT5 byte-level** thay vì SentencePiece — robust
   hơn với corruption ký tự cấp byte (literature confirms).
5. **Add copy mechanism** vào architecture (Pointer-Generator) — cho
   phép model copy chữ đúng từ input thay vì phải regenerate. Yêu
   cầu retrain từ đầu.

#### Decision sau phân tích

- **KHÔNG ship `vit5-ocr-correct` model.** Negative-result kể cả với
  guards.
- **KHÔNG enable post-correct mặc định trong `nom.doc.ocr`** — nó
  không cải thiện trên handwriting, neutral trên printed in sạch.
- **Document opt-in path** với confidence gate cho user có printed
  scan với baseline ~5-30 % CER (band post-correct chứng minh hoạt
  động được trong literature).
- **Pivot ưu tiên** sang fix OCR engine — đã chọn VietOCR cho
  handwriting (-37.5 pp vs Tesseract). Bước tiếp là TrOCR-VN
  fine-tune (start từ `microsoft/trocr-base-handwritten`, swap
  tokenizer sang BARTpho-syllable) để đẩy handwriting CER xuống
  dưới 20 %.

Reproduce postmortem analysis:

```bash
python training/ocr_correction/analyze_failure.py --n-samples 200
python training/ocr_correction/bench_with_guards.py \
    --json benchmarks/results/baseline_ocr_post_correct_real_guarded.json
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
