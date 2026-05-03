# Trích xuất thực thể

Tìm và phân loại các tên thực thể trong đoạn văn tiếng Việt — người,
tổ chức, nơi chốn, ngày, tiền tệ, **điều luật**, **CMND/CCCD**, **số
điện thoại VN**. Trang này tập trung vào giao diện trích xuất; xem
[`nlp.md`](./nlp.md) cho thư viện đầy đủ (NER + cảm xúc + nhận diện
ngôn ngữ).

## TL;DR — gợi ý của chúng tôi

Hai bộ thực thể, chọn theo nhu cầu:

| Bộ | Bao gồm | Khi nào chọn |
| --- | --- | --- |
| **Chuẩn** *(mặc định)* | PER, ORG, LOC, DATE, MONEY | Hồ sơ doanh nghiệp, tin tức, hồ sơ y tế |
| **Pháp lý** | Chuẩn + LAW_REF, ID_VN, PHONE_VN | Hợp đồng, công văn, đơn từ pháp lý |

Backend mặc định: regex (nhanh, deterministic, không cần model). Cần
độ chính xác cao hơn, đổi sang HF model qua plugin doanh nghiệp.

## Cách dùng

### Trong giao diện web

Mở **Trích xuất thực thể** ở thanh điều hướng bên trái. Dán đoạn văn
hoặc bấm một trong các nút mẫu (`HOÁ ĐƠN`, `HỢP ĐỒNG PHÁP LÝ`,
`HỢP ĐỒNG + LUẬT SỐ`). Chọn **Bộ thực thể** ở cột phải:

- **Chuẩn** — `PER / ORG / LOC / DATE / MONEY`.
- **Pháp lý** — `Chuẩn` cộng `LAW_REF` (luật, điều, khoản), `ID_VN`
  (CMND / CCCD), và `PHONE_VN`.

Bấm **Trích**.

Kết quả hiển thị mỗi span tô màu theo loại, kèm vị trí ký tự (start,
end) và độ tin cậy.

### Gọi trực tiếp qua API HTTP

```bash
curl -X POST http://localhost:8080/api/tools/nlp/ner \
  -H "Content-Type: application/json" \
  -d '{
        "text": "Theo Nghị định 13/2023/NĐ-CP, ông Nguyễn Văn A (CMND 012345678901) chuyển 1.500.000 VND ngày 02/05/2026.",
        "preset": "legal"
      }'
```

Trả về:

```json
{
  "spans": [
    {"label": "LAW_REF", "text": "Nghị định 13/2023/NĐ-CP", "start": 5, "end": 28},
    {"label": "PER",     "text": "Nguyễn Văn A",            "start": 33, "end": 45},
    {"label": "ID_VN",   "text": "012345678901",            "start": 52, "end": 64},
    {"label": "MONEY",   "text": "1.500.000 VND",           "start": 75, "end": 88},
    {"label": "DATE",    "text": "02/05/2026",              "start": 95, "end": 105}
  ]
}
```

## Bộ pháp lý — chi tiết

Ba lớp thực thể bổ sung được thêm vì thực tế hợp đồng VN cần chúng:

### `LAW_REF`

Phát hiện tham chiếu pháp luật theo mẫu: `<Loại> <số>/<năm>/<cơ quan>`.

| Mẫu | Bắt được | Bỏ qua |
| --- | --- | --- |
| `Luật 134/2025/QH15` | ✓ | |
| `Nghị định 13/2023/NĐ-CP` | ✓ | |
| `Thông tư 02/2024/TT-BTTTT` | ✓ | |
| `Điều 8 Luật 134/2025` | ✓ (gộp một LAW_REF) | |
| `Điều 8` (không có số luật) | | ✗ — bỏ qua, ngữ cảnh không đủ |

### `ID_VN`

CMND 9 chữ số, CCCD 12 chữ số. Lọc bằng độ dài + checksum khi áp
dụng được:

| Đầu vào | Phát hiện |
| --- | --- |
| `CMND: 012345678` | ✓ ID_VN |
| `CCCD 012345678901` | ✓ ID_VN |
| `024089001234` (12 chữ số đầu) | ✓ ID_VN |
| `01234567` (8 chữ số) | ✗ — không khớp độ dài |

### `PHONE_VN`

Số điện thoại VN — di động 10 chữ số bắt đầu bằng `03/05/07/08/09`,
hoặc đầu số quốc gia `+84`:

| Đầu vào | Phát hiện |
| --- | --- |
| `0987654321` | ✓ PHONE_VN |
| `+84 987 654 321` | ✓ PHONE_VN |
| `0241234567` (cố định Hà Nội) | ✓ PHONE_VN |
| `1234567890` | ✗ — không khớp đầu số VN |

## Cách hoạt động

`nom.nlp.ner` dùng `RegexNERModel` ở v0:

1. Chạy regex song song cho mỗi loại thực thể.
2. Khử trùng overlap — nếu hai span chồng nhau, chọn loại có precedence
   cao hơn (LAW_REF > ORG > MONEY > DATE > PHONE_VN > ID_VN > PER > LOC).
3. Trả về danh sách `NERSpan(label, text, start, end, confidence)`.

Không dùng model trong v0 — nhanh (~5 ms/đoạn), deterministic, không
cần GPU. Thiếu sót: không bắt được PER (tên người) tốt vì regex tên
VN khó. Khi cần PER chính xác, đổi sang `HFNERModel(model_id="vinai/phobert-large-finetune-vi-ner")`
— xem [`nlp.md`](./nlp.md).

## Giới hạn đã biết

- **PER kém.** Regex không phân biệt "Nguyễn Văn A" (tên) với "Nguyễn
  Du" (tên người mất từ thế kỷ 18 đang được trích trong văn bản pháp
  lý). Cần PhoBERT-NER cho production.
- **LAW_REF chỉ bắt mẫu chuẩn.** Tham chiếu pháp luật có cấu trúc
  bất thường (viết tắt, gộp số) có thể bị bỏ sót. Bao phủ ~85 % công
  văn VN hiện đại.
- **ID_VN không xác minh checksum CCCD.** Có thể có false positive với
  chuỗi 12 chữ số ngẫu nhiên. Hợp lý cho text mining; với verification
  bắt buộc dùng API VNeID.
- **PHONE_VN bỏ qua đầu số quốc tế ngoài VN.** Chỉ tập trung +84.

## Tích hợp với tác vụ khác

| Pipeline | NER ở đâu |
| --- | --- |
| Hợp đồng → bảng tóm tắt | OCR → NER pháp lý → Tóm tắt với ngữ cảnh thực thể |
| Đơn từ y tế | OCR → NER chuẩn (PER + DATE) → Phân loại rủi ro |
| Audit log nội bộ | Chat → NER chuẩn (PER + ORG + DATE) → Lưu vào space |

## Liên quan

- [`nlp.md`](./nlp.md) — toàn bộ thư viện NLP (NER + cảm xúc + nhận
  diện ngôn ngữ) + cách gắn HF model qua plugin.
- [Phân loại rủi ro](./compliance.md) — pipeline xuôi dòng dùng NER.
- [Tóm tắt](./summarize.md) — gợi ý thực thể quan trọng cho prompt.
