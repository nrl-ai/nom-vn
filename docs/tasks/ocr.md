# OCR tiếng Việt

Trích văn bản từ ảnh hoặc PDF quét. Lựa chọn mặc định:
**Tesseract 5 + bộ dữ liệu `vie`** — đo được nhanh hơn và chính xác
hơn các VLM cho dòng chữ in sạch. Nếu PDF đã có lớp văn bản, dùng
[`pdf-extraction`](/tasks/pdf-extraction) thay cho OCR.

## Chọn engine theo loại ảnh (đo 2026-05-01)

Đo trên 200 ảnh chữ viết tay (`brianhuster/VietnameseOCRdataset`)
và 70 ảnh chữ in (`benchmarks/data/synthetic_ocr_vi/{clean,noisy,hard}`).

| Loại ảnh | Khuyến nghị | CER | Độ trễ | Khi nào chọn khác |
|---|---|---:|---:|---|
| 🖨️ **Bản in sạch** (A4 quét sắc nét, phông chuẩn) | **Tesseract `vie`** | **0,00 %** | 80 ms | Không cần — Tesseract gần như không sai |
| 🖨️ **Bản in nhiễu nhẹ** (mờ 1-2 px) | **Tesseract `vie`** | **0,70 %** | 80 ms | Đổi VietOCR nếu cần tìm kiếm chùm; tránh PaddleOCR/RapidOCR vì cả hai dùng chung mô hình Latin chung và làm rớt dấu |
| 🖨️ **Quét kém** (giấy cũ, mực phai, nén JPEG) | **VietOCR** | **29,00 %** | 246 ms | Tesseract làm dự phòng khi cần độ trễ thấp |
| ✍️ **Chữ viết tay** (ghi chép, vở học sinh) | **VietOCR** | **31,82 %** | 246 ms | PaddleOCR đứng thứ 3 (59,4 %), kém VietOCR ~28 pp; PaddleOCR không có mô hình nhận diện riêng cho tiếng Việt |
| 📋 **Biểu mẫu / hoá đơn / thẻ ID** | **VLM** (Qwen2.5VL, Gemma3-Vision) | Chưa có ngữ liệu phù hợp | 1,4-2 s | Đã cắt được trường thì dùng Tesseract/VietOCR. Muốn đo cần xây ngữ liệu biểu mẫu tiếng Việt có nhãn |
| 📷 **Ảnh chụp điện thoại** (nghiêng, ánh sáng kém) | **VLM** ở cấp tài liệu, hoặc tiền xử lý rồi VietOCR | Chưa có ngữ liệu phù hợp | 1,4-2 s | Muốn đo cần ngữ liệu ảnh điện thoại có nhãn (MC-OCR 2021 chưa rõ giấy phép). VLM vẫn là khuyến nghị cho lớp này |
| 📜 **Sách cổ** (1850-2000) | Chưa đo | — | — | Để sau; VieBookRead giấy phép afl-3.0, chưa đưa vào bộ đo |
| 📄 **PDF số hoá sẵn** (có lớp văn bản) | **`nom.doc.pdf`** (pypdfium2) | 99,81 % trùng ký tự | < 1 ms | Đây không phải OCR |

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

**Tóm gọn lại:**

- *Chữ in sạch / quét tốt* → Tesseract `vie`. CER 0-1 %, 80 ms một dòng.
- *Chữ viết tay tiếng Việt* → **VietOCR** vgg_transformer. CER 32 %
  trên ngữ liệu viết tay của brianhuster, so với Tesseract 69 % —
  **giảm 37,5 pp tuyệt đối, ~54 % tương đối**.
- *Tài liệu / biểu mẫu / thẻ ID / bố cục phức tạp* → VLM (Qwen2.5VL,
  Gemma3-Vision) — chỉ ở cấp tài liệu, không dùng cho dòng đơn
  (xem cảnh báo bên dưới).
- *PDF có lớp văn bản* → `nom.doc.pdf` qua pypdfium2, không cần OCR.

## So sánh đầy đủ các engine (đo 2026-05-01)

| Backend | Giấy phép | CER ảnh in sạch | CER ảnh in nhiễu | CER quét kém | CER viết tay | Độ trễ p50 |
|---|---|---:|---:|---:|---:|---:|
| **Tesseract 5 + `vie`** | Apache 2.0 | **0,00 %** ⭐ | **0,70 %** ⭐ | 30,34 % | 69,34 % | 80 ms |
| **VietOCR vgg_transformer** | Apache 2.0 | 1,41 % | 3,37 % | **29,00 %** ⭐ | **31,82 %** ⭐ | 240 ms |
| EasyOCR | Apache 2.0 | 1,42 % | 4,87 % | 87,09 % | 71,52 % | 35-60 ms |
| PaddleOCR PP-OCRv5 (latin_mobile_rec) | Apache 2.0 | 24,70 % | 31,33 % | 86,13 % | 59,43 % | 1170-1260 ms |
| RapidOCR (ONNX, port của PaddleOCR) | Apache 2.0 | 63,97 % | 77,83 % | 100,00 % | 97,20 % | 130-250 ms |
| TrOCR base-handwritten (chỉ tiếng Anh, làm tham chiếu) | MIT | 32,89 % | 38,07 % | 93,76 % | 75,89 % | 180-280 ms |
| `qwen2.5vl:7b` (VLM qua Ollama) | Apache 2.0 (mô hình) | 33,17 % | 29,90 % | 81,37 % | 67,53 % | 320-610 ms |
| Surya OCR | open-RAIL-M | Chưa đo (giấy phép không đạt) | — | — | — | — |

**Phát hiện chính (đo 2026-05-01):**

- **VietOCR là lựa chọn đúng cho chữ viết tay tiếng Việt.** Giảm
  37,5 pp CER so với Tesseract (69,34 → 31,82 %), tương ứng -54 %
  tương đối.
- **Tesseract vẫn là lựa chọn đúng cho chữ in sạch.** CER 0,00 %
  trên ảnh in sạch tự sinh. VietOCR đạt 1,41 %, không bõ đánh đổi
  tốc độ (Tesseract nhanh hơn 3 lần).
- **PaddleOCR PP-OCRv5 đứng thứ 3-4 trên *mọi* loại ảnh tiếng
  Việt.** Đo lại 2026-05-01 với pipeline mặc định, bỏ tiền xử lý
  tài liệu, gọi riêng `TextRecognition`, và
  `latin_PP-OCRv5_server_rec`; đo lại toàn bộ ngày 2026-05-02.
  Vấn đề ở thiết kế: **PP-OCRv5 không có mô hình nhận diện riêng
  cho tiếng Việt**; `lang='vi'` chỉ tải `latin_PP-OCRv5_mobile_rec`
  — mô hình Latin chung nhận được chữ cái nhưng rớt dấu (sắc /
  huyền / hỏi / ngã / nặng) ở tỉ lệ cao, ngay cả trên ảnh in sạch
  (24,70 % CER vs Tesseract 0,00 %).
- **RapidOCR là bản port ONNX của PaddleOCR — cùng lỗi.** Mặc
  định của Docling `ocr_engine='rapidocr'` cũng không dùng được
  cho tiếng Việt. Trên ảnh in sạch còn rớt dấu (63,97 % CER); trên
  ảnh cắt dòng chữ viết tay gần như không nhận được gì (97,20 % CER).
- **Surya OCR không qua kiểm tra giấy phép.** Mô hình open-RAIL-M
  không tương thích với bộ công cụ Apache 2.0. Bỏ qua dù chất
  lượng cạnh tranh.

Tệp JSON nguồn:
[`baseline_ocr_engines.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_ocr_engines.json)
(viết tay, n=200) ·
[`baseline_ocr_engines_printed.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_ocr_engines_printed.json)
(in sạch / nhiễu / khó, lưới đầy đủ) ·
[`baseline_ocr_engines_per_register.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_ocr_engines_per_register.json)
(tóm tắt theo loại văn bản).

Tái lập:

```bash
# Viết tay
python benchmarks/accuracy/bench_ocr_engines.py \
    --json benchmarks/results/baseline_ocr_engines.json
# Chữ in (sạch / nhiễu / khó)
python benchmarks/accuracy/bench_ocr_engines_printed.py \
    --json benchmarks/results/baseline_ocr_engines_printed.json
```

## Quy trình thực dụng theo loại dữ liệu

### Mẫu 1: Văn bản in tiếng Việt (mặc định)

```python
from nom.doc.ocr import TesseractOCR

ocr = TesseractOCR(lang="vie")
text = ocr.read("scan.png")
# 0-1 % CER, ~80 ms/ảnh
```

Dùng cho ảnh quét tài liệu hành chính, hợp đồng in, sách giáo khoa,
ảnh quét báo chí. Tesseract trên ảnh in sạch gần như hoàn hảo —
không có lựa chọn thay thế đáng cân nhắc.

### Mẫu 2: Chữ viết tay tiếng Việt

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

Dùng cho ghi chép cá nhân, biểu mẫu điền tay, vở học sinh, chú thích
trên tài liệu. **VietOCR thắng tuyệt đối** — không có engine nào
trong số đã đo gần ngang. PaddleOCR PP-OCRv5 đứng thứ 3 ở 59,4 %
CER (gấp ~1,9 lần lỗi của VietOCR và chậm 5 lần). RapidOCR gần như
thất bại hoàn toàn (97 % CER) — bộ phát hiện không bắt được dòng
chữ viết tay.

### Mẫu 3: Biểu mẫu / hoá đơn / thẻ ID / bố cục phức tạp

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

Dùng VLM khi tài liệu có cấu trúc và cần hiểu ngữ cảnh. VLM nhìn
toàn bộ ảnh, hiểu bố cục biểu mẫu. **Cảnh báo:** không dùng VLM
cho ảnh cắt dòng đơn — VLM ảo giác trên dòng đơn (xem cảnh báo
bên dưới).

### Mẫu 4: PDF số hoá sẵn (có lớp text)

```python
from nom.doc.pdf import extract_text
text = extract_text("contract.pdf")
# 99.81 % char overlap, 2.35 M chars/s, không phải OCR
```

**Không bao giờ chạy OCR trên PDF số hoá sẵn** — văn bản đã có sẵn.
Xem [`/tasks/pdf-extraction`](/tasks/pdf-extraction).

### Mẫu 5: Tự động chọn engine theo độ tin cậy

Cho ứng dụng có ảnh trộn lẫn nhiều loại văn bản chưa biết trước:

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

Tự động chọn engine dựa trên độ tin cậy của Tesseract: ảnh in sạch
chạy đường nhanh, ảnh viết tay rẽ sang VietOCR.

## Cảnh báo về sự "ảo giác" của VLM

Trên ảnh cắt dòng đơn (sắp đặt OCR điển hình), Qwen2.5VL 7B đạt
**31 % CER** — gấp 6 lần Tesseract trên ảnh in sạch. Lý do: tiên
nghiệm ngôn ngữ lấn át khi tín hiệu thị giác hẹp. VLM là công cụ
đúng cho **hiểu tài liệu** (biểu mẫu, hoá đơn, thẻ ID, chữ viết
tay nguyên trang) chứ không phải ảnh cắt dòng chữ in sạch.

`Surya OCR` không qua kiểm tra giấy phép: mã nguồn GPL-3 và mô hình
open-RAIL-M không tương thích với mục tiêu phân phối Apache 2.0 của
chúng tôi. Chúng tôi **không phát hành** Surya — bỏ qua dù chất
lượng cạnh tranh.

## Quy trình của chúng tôi

```python
from nom.doc.ocr import TesseractOCR
from PIL import Image

ocr = TesseractOCR(lang="vie", config="--psm 6")  # PSM 6 = khối văn bản đồng nhất
text = ocr.read(Image.open("scan.png"))
```

Lớp bao quanh `pytesseract` cung cấp:

- Tiền xử lý tự động (cân nghiêng nhẹ, chuẩn hoá độ tương phản) khi `auto_preprocess=True`
- Chuẩn hoá NFC cho đầu ra
- Dự phòng theo quy tắc nếu Tesseract không trả về gì cho dòng (ảnh trắng / quá nhỏ)

## Kết quả đã đo

Đo trên `benchmarks/data/synthetic_ocr_vi/` (40 ảnh PNG, nhãn chuẩn,
trộn ảnh sạch + nhiễu). Metric: CER (tỉ lệ lỗi ký tự) tính trên chuỗi
ký tự đã NFC. CER-dấu tính riêng cho dấu phụ kết hợp (xem
[docs/benchmark.md](/benchmark)).

| Backend | CER | CER-dấu | Độ trễ p50 |
|---|---:|---:|---:|
| Tesseract 5 + `vie` | **5,53 %** | 8,21 % | 80 ms |
| EasyOCR | 9,39 % | 14,88 % | 250 ms |
| qwen2.5vl:7b VLM | 31,07 % | 38,45 % | 1,4 s |

Tệp baseline JSON: `benchmarks/results/baseline_ocr_*.json`.

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

### Phân tích sâu thất bại — vì sao hậu sửa không cứu được chữ viết tay (2026-05-01)

Đã thử tinh chỉnh `nrl-ai/vn-spell-correction-base` trên 9 626 cặp
`(đầu ra Tesseract, nhãn chuẩn)` từ
[`brianhuster/VietnameseOCRdataset`](https://huggingface.co/datasets/brianhuster/VietnameseOCRdataset)
(Apache 2.0, chữ viết tay). Đo trên 200 ảnh tách riêng cho phần thử
nghiệm (không nằm trong dữ liệu huấn luyện):

| Quy trình | CER | WER | giúp / hại |
|---|---:|---:|---|
| Tesseract `vie` (baseline) | **69,34 %** | 98,95 % | — |
| + sửa chính tả base (mô hình có sẵn) | 69,98 % (+0,64) | 98,56 % (-0,40) | 35 / 103 |
| + ocr-correct sau tinh chỉnh (3 epoch) | **81,80 % (+12,46)** | 101,26 % (+2,31) | 14 / 173 |

**Cả hai cách hậu sửa đều làm tệ hơn.** Bản tinh chỉnh tệ nhiều
hơn — mô hình học bịa văn bản tiếng Việt nghe có vẻ hợp lý từ
rác, không sửa.

Ví dụ thất bại điển hình:
```
GOLD: khung cảnh kinh tế, xã hội và định chế.
RAW : vhuag cảnh kuÄ tố, xá đậu v3 đụnh chế   (CER 33 %)
PP  : và những cảnh sát, xã hội và 3            (CER 51 %)
```

Mô hình bịa "cảnh sát" thay vì "kinh tế".

**Nguyên nhân gốc:** Tesseract `vie` không được huấn luyện cho chữ
viết tay tiếng Việt; CER 70 % không đủ tín hiệu để khôi phục. Đây
là kiểu lỗi "ảo giác do hậu sửa quá mức" mà
[Kanerva et al. 2025](https://arxiv.org/html/2502.01205v1) đã báo
cáo trên tiếng Phần Lan (LLM hậu OCR giảm CER -19 % đến -76 %,
*tệ hơn* baseline).

#### Các kiểu thất bại đã đo (analyze_failure.py)

Script chẩn đoán `training/ocr_correction/analyze_failure.py` đã
phân tích 200 ảnh thử nghiệm:

| Chỉ số | Bản base có sẵn | Bản tinh chỉnh ocr-correct |
|---|---:|---:|
| **% từ trong đầu ra hậu sửa KHÔNG có trong OCR thô** (chỉ số ảo giác) | 39,5 % | **91,3 %** |
| Độ dài trung bình đầu ra (ký tự, nhãn chuẩn = 67) | 46,4 | 39,3 |
| Số đầu ra trùng lặp (sụp về vài chuỗi) | 0 | 2 (`. `, ...) |
| Δ CER trên nhóm CER thô 50-70 %, n=105 | +1,45 pp | **+15,58 pp** |
| Δ CER trên nhóm CER thô 70 %+, n=88 | -0,66 pp | **+7,70 pp** |

**91 % các từ trong đầu ra của bản tinh chỉnh không tồn tại trong
đầu vào gốc** — mô hình đang sinh tự do thay vì sửa.

#### Cơ chế chặn lỗi khi suy luận giảm hồi quy nhưng không khắc phục được

Thử thêm bộ chặn lỗi (tìm kiếm chùm 4, cấm n-gram lặp = 3, ràng buộc
độ dài đầu ra theo độ dài đầu vào, ngưỡng độ tin cậy dựa trên số
ký tự dấu phụ tiếng Việt):

| Quy trình | CER | WER | Δ so với thô |
|---|---:|---:|---:|
| Tesseract đầu ra thô | 69,34 % | 98,95 % | baseline |
| + spell-correction-base (giải mã tham lam) | 69,98 % | 98,56 % | +0,64 / -0,40 |
| + spell-correction-base (có chặn lỗi) | 70,40 % | 99,19 % | +1,06 / +0,24 |
| + ocr-correct tinh chỉnh (giải mã tham lam) | 81,80 % | 101,26 % | +12,46 / +2,31 |
| + ocr-correct tinh chỉnh (có chặn lỗi) | 78,32 % | 98,91 % | **+8,98** / **-0,04** |

Bộ chặn lỗi giảm hồi quy của bản tinh chỉnh từ +12,46 → +8,98 pp CER
(cải thiện 3,5 pp) nhưng không đảo ngược được kết luận: **hậu sửa
trên Tesseract chữ viết tay không thể có lợi ròng**.

#### Nguyên nhân gốc

**Baseline OCR ở mức CER 70 % là quá xấu để hậu sửa cứu được.** Khi
7/10 ký tự sai, không còn đủ tín hiệu để mô hình khôi phục nội dung
gốc. Kết quả tốt nhất là "không làm gì" (giữ đầu ra thô) — bất kỳ
bước hậu sửa nào cũng chỉ thêm rủi ro ảo giác.

Tài liệu tham khảo:

- [Tran et al. 2024](https://arxiv.org/html/2410.13305) báo cáo
  WER 27 % → 18 % khi huấn luyện trực tiếp trên cặp `(Tesseract,
  nhãn chuẩn)` — nhưng baseline của họ là **ảnh quét bản in
  ~30 % CER**, không phải chữ viết tay 70 %.
- [Kanerva et al. 2025](https://arxiv.org/html/2502.01205v1) báo cáo
  LLM hậu OCR trên tiếng Phần Lan: CER -19 % đến -76 % (tệ hơn
  baseline) trên một số ngữ liệu — chính xác kiểu lỗi chúng tôi gặp.

### Docling và bộ công cụ bên ngoài — không có lối tắt riêng cho tiếng Việt

[Docling](https://github.com/DS4SD/docling) (IBM Research) là bộ công
cụ chuyển đổi tài liệu phổ biến nhất 2026, nhưng **không xuất bản
mô hình OCR riêng**: nó uỷ thác qua plug-in cho EasyOCR (mặc định),
Tesseract (`ocr_engine='tesseract'`), hoặc RapidOCR
(`ocr_engine='rapidocr'`). Cả ba đều đã có trong bảng so sánh ở
trên — không có engine "ẩn" nào để khai thác. Giá trị thêm của
Docling nằm ở **bố cục** (RT-DETR) và **bảng biểu** (TableFormer),
không phải OCR. Với chữ viết tay tiếng Việt, dùng VietOCR trực tiếp;
với tài liệu in có cấu trúc (báo cáo, bảng biểu), Docling + Tesseract
`vie` là tổ hợp đúng.

### Ngữ liệu thử nghiệm bổ sung — chưa đo

Ngoài `brianhuster/VietnameseOCRdataset` (chữ viết tay, đang dùng) và
`benchmarks/data/synthetic_ocr_vi/` (chữ in, sinh tại chỗ), một số
ngữ liệu công khai tiếng Việt khác có thể bổ sung:

| Ngữ liệu | Giấy phép | Loại văn bản | Quy mô | Trạng thái |
|---|---|---|---|---|
| [`brianhuster/VietnameseOCRdataset`](https://huggingface.co/datasets/brianhuster/VietnameseOCRdataset) | Apache 2.0 | Chữ viết tay (cắt dòng) | 7 296 ảnh | ✅ Đang dùng (200 ảnh thử nghiệm) |
| [`iAmHieu2012/vietnamese-ocr-dataset-aggregated`](https://huggingface.co/datasets/iAmHieu2012/vietnamese-ocr-dataset-aggregated) | MIT | Ảnh quét trang in | ~3 500 trang | 📋 Hướng tới (cấp trang, cần phát hiện dòng trước) |
| `VieBookRead` | afl-3.0 | Sách quét (1850-2000) | Chưa rõ | 📋 Cho loại văn bản cổ |
| `MC-OCR 2021` | Cần xác thực | Hoá đơn | Chưa rõ | 📋 Giấy phép chưa rõ — kiểm tra trước khi dùng |
| `manhha2502/Vietnamese_Handwriting_OCR` | Cần xác thực | Chữ viết tay | Chưa rõ | 📋 Giấy phép chưa rõ |

`benchmarks/data/synthetic_ocr_vi/` vẫn là nguồn dữ liệu cố định
cho chữ in (sinh tại chỗ, CC0). `iAmHieu2012/...` là ảnh quét thật
giấy phép MIT, sẽ là phép đo thực cho chữ in khi cần đánh giá khả
năng tổng quát ngoài dữ liệu sinh.

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
