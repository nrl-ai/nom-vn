# OCR chữ viết tay

Đọc chữ viết tay tiếng Việt từ ảnh — biểu mẫu, ghi chú, phiếu bài tập,
mặt sau CMND/CCCD. Khác với OCR chữ in (xem [Chuyển định dạng](./convert.md)),
chữ viết tay cần một mô hình thị giác đa phương thức (VLM) chứ không
phải engine OCR truyền thống.

## TL;DR — gợi ý của chúng tôi

`pip install "nom-vn[ocr-handwriting]"` để có sẵn `transformers` +
`torch` + `torchvision` + `timm` + `pillow`. Mặc định dùng
[`5CD-AI/Vintern-1B-v3_5`](https://huggingface.co/5CD-AI/Vintern-1B-v3_5)
(MIT, 0.9 B tham số, safetensors). Lần đầu tải khoảng 1.8 GB.

Yêu cầu: GPU 4–6 GB VRAM cho tốc độ chấp nhận được; CPU chạy được
nhưng mất 1–2 phút mỗi ảnh.

### Đo nội bộ trên `synthetic_ocr_vi` (2026-05-03)

Bench đầu tay trên dòng chữ in tiếng Việt (đẩy qua Vintern, không
phải Tesseract — để đo phần "Vintern xử lý đúng dòng in clean như
thế nào"):

| Điều kiện | n | Mean CER | Exact-match |
|---|---:|---:|---:|
| `clean` (1 font, nền trắng) | 20 | **0.47 %** | 16/20 |
| `noisy` (cùng nội dung + nhiễu/jitter) | 20 | **0.37 %** | 17/20 |

Phần lớn "lỗi" còn lại là biến thể chính tả VN hợp lệ (`hoà` ↔ `hòa`)
mà CER tính là khác biệt. n=20 còn nhỏ — bench trên 200+ ảnh trước khi
publish con số "VN handwriting CER" chính thức.

Tập eval ([`nrl-ai/vn-synthetic-ocr`](https://huggingface.co/datasets/nrl-ai/vn-synthetic-ocr),
CC0) đã publish trên HF. Baseline JSON:
[`benchmarks/accuracy/vintern_ocr_clean_baseline.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/accuracy/vintern_ocr_clean_baseline.json)
+ [`vintern_ocr_noisy_baseline.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/accuracy/vintern_ocr_noisy_baseline.json).

## Cách dùng

### Trong giao diện web

Mở **OCR chữ viết tay** ở thanh điều hướng bên trái. Kéo thả ảnh
(`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) hoặc bấm
**Chọn ảnh**. Bấm **OCR**. Lần đầu chạy mất 30–60 giây để tải mô
hình; lần sau ~5–15 giây mỗi ảnh trên GPU, hoặc 1–2 phút trên CPU.

### Gọi trực tiếp qua API HTTP

```bash
curl -X POST http://localhost:8080/api/jobs/handwriting-ocr \
  -F "file=@phieu_dang_ky.jpg"
# → { "id": "<job-id>", "status": "queued", ... }
```

Tác vụ chạy nền — theo dõi qua [Hàng đợi xử lý](./jobs.md) hoặc
`GET /api/jobs/{id}`.

## Cách hoạt động

`nom.ocr.handwriting` là wrapper quanh Vintern-1B-v3_5:

1. **Đọc ảnh** — Pillow load + chuyển sang RGB. Truyền cả trang, không
   cắt từng dòng.
2. **Prompt** — `"Đọc và trích xuất toàn bộ chữ viết tay trong ảnh.
   Giữ nguyên xuống dòng và bố cục."`
3. **Generate** — temperature 0, max 2048 token đầu ra.
4. **Decode + NFC** — chuẩn hoá Unicode tổ hợp dấu trước khi trả về.

### Vì sao truyền cả trang, không cắt từng dòng

VLM ảo trên line crop < 60 px chiều ngắn — cạm bẫy đã đo trên
`qwen2.5vl:7b` (CER 33 % với chữ in clean ở line crop, vs 5 % cho
Tesseract). Truyền cả trang giữ ngữ cảnh không gian, mô hình tự suy
luận đường đọc.

## Khi nào chọn cái gì

| Đầu vào | Khuyến nghị | Lý do |
| --- | --- | --- |
| Chữ viết tay | **Vintern-1B-v3_5** | Specialist VN handwriting |
| Chữ in clean (PDF / scan) | **Tesseract** qua `nom convert` | CER 0 % trên dòng in sạch, 100 × nhanh hơn VLM |
| Form lai (in + viết tay) | **Vintern** trước, **Tesseract** lại nếu phần in cần độ chính xác cao | Vintern bao quát; Tesseract chốt phần in |
| Hồ sơ y tế viết tay | Vintern + xác nhận thủ công | Vintern chưa fine-tune trên y tế VN; CER ước ~20 % |

Vintern không thay thế Tesseract cho mọi trường hợp — nó **bổ sung**
cho phần Tesseract không làm được (chữ viết tay).

## Giới hạn đã biết

+ **Đã đo trên chữ in synthetic (CER 0.47 % clean / 0.37 % noisy, n=20),
  chưa đo độc lập trên chữ viết tay thực.** Mọi con số chữ-viết-tay
  bên dưới là **ước lượng**, chưa benchmark first-party:
  + Chữ in scan rõ: CER ≈ 5 % (cao hơn synthetic vì layout phức tạp)
  + Chữ viết tay người trưởng thành nét rõ: CER ≈ 15 % (ước lượng)
  + Chữ viết tay nhanh hoặc nét nguệch ngoạc: CER ≈ 30 %+ (ước lượng)

  Bench đầu tay trên handwriting thật là task Tier 2 — sẽ chạy trên
  `brianhuster/VietnameseOCRdataset` (~7 k ảnh, Apache-2.0) và
  cập nhật con số ở đây trong cùng commit như JSON baseline.
+ **Phụ thuộc chất lượng ảnh.** Ảnh mờ, tối, hoặc nghiêng > 15° làm
  giảm chất lượng đáng kể. Crop sạch đầu vào trước.
+ **Không xử lý cấu trúc form.** Vintern trả về văn bản tuyến tính,
  không nhận diện ô / cột / nhãn. Cho biểu mẫu có cấu trúc, kết hợp
  với rule-based field-extraction sau OCR.
+ **Latency cao.** 5–15 giây/ảnh trên GPU 8 GB là điển hình. Cho
  pipeline hàng loạt nên dùng [Hàng đợi](./jobs.md) thay vì chờ
  request HTTP.
+ **Tiếng Việt thuần;** mô hình đa ngôn ngữ về cơ bản nhưng chưa được
  đo trên tài liệu lai EN/VN.

## Mô hình thay thế

| Mô hình | License | Khi nào chọn |
| --- | --- | --- |
| `5CD-AI/Vintern-1B-v3_5` *(mặc định)* | MIT | VN handwriting tiêu chuẩn |
| `5CD-AI/Vintern-3B` | MIT | Cần chất lượng cao hơn, có VRAM 8 GB+ |
| `qwen2.5-vl:7b` qua Ollama | Apache 2.0 | Đa ngôn ngữ, không cần GPU; kém Vintern trên VN |

## Liên quan

+ [Chuyển định dạng (OCR chữ in)](./convert.md) — Tesseract + Pdfium.
+ [Khôi phục dấu](./diacritic-restoration.md) — chạy sau OCR để bù
  dấu Tesseract bỏ sót.
+ [Sửa chính tả](./spell-correction.md) — lượt cuối làm sạch lỗi OCR.
