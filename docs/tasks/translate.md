# Dịch thuật

Dịch văn bản và **giữ nguyên định dạng** giữa tiếng Việt và tiếng Anh —
local-first, an toàn cho tài liệu nhạy cảm (hợp đồng, báo cáo nội bộ,
hồ sơ y tế).

## Định dạng được hỗ trợ

| Loại tệp | Trạng thái | Ghi chú |
| --- | --- | --- |
| `.docx` | Đầy đủ | Heading, danh sách, bảng, header / footer, hyperlink |
| `.xlsx` | Đầy đủ | Mọi ô chuỗi; số / công thức / định dạng giữ nguyên |
| `.pptx` | Đầy đủ | Slide, ô bảng, ghi chú, shape lồng nhau |
| `.txt`, `.md`, `.rst` | Đầy đủ | Tách theo đoạn (dòng trắng); giữ heading markdown |
| `.pdf`, ảnh | Qua `nom convert` | Đổi sang `.docx` rồi dịch lại |

## Cách dùng

### Trong giao diện web

Mở **Dịch thuật** ở thanh sidebar Playground.

- **Văn bản** — dán đoạn cần dịch, chọn hướng (Việt ↔ Anh), bấm Dịch.
- **Tệp** — kéo thả `.docx` / `.xlsx` / `.pptx` / `.txt` / `.md` /
  `.rst`. Tệp dịch tự động tải về với tên `<gốc>.<ngôn-ngữ-đích>.<đuôi>`.

### Dòng lệnh (CLI)

```bash
# Mặc định: tiếng Việt → tiếng Anh, dùng LLM cài sẵn (qwen3:8b)
nom translate hop-dong.docx

# Đổi hướng + chỉ định mô hình HF chuyên dụng
nom translate report.xlsx --src en --tgt vi \
    --backend hf --model google/madlad400-3b-mt

# Đầu ra cụ thể
nom translate slides.pptx --output slides_vi.pptx
```

### API HTTP

```bash
# Một đoạn ngắn
curl -X POST http://localhost:8080/api/tools/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hợp đồng vô hiệu", "source": "vi", "target": "en"}'

# Tệp
curl -X POST http://localhost:8080/api/tools/translate/file \
  -F "file=@contract.docx" \
  -F "source=vi" -F "target=en" \
  -o contract_en.docx
```

Endpoint trả về tệp dịch trực tiếp; thống kê trong header
`X-Translation-Stats` (số đoạn dịch / bỏ qua / lỗi, số ký tự vào / ra).

## Cách hoạt động

Dịch giữ định dạng dùng **walker theo cấu trúc tệp**, không đi qua
trung gian như XLIFF — đơn giản hơn và đủ tốt cho 95 % trường hợp:

1. Mở tệp bằng thư viện gốc của Python (`python-docx`, `openpyxl`,
   `python-pptx`).
2. Duyệt cây cấu trúc — đoạn (paragraph), ô (cell), shape, slide.
3. Mỗi đơn vị → gọi `Translator` (LLM trò chuyện hoặc mô hình HF
   chuyên dụng).
4. Ghi văn bản đã dịch ngược trở lại vào đúng đơn vị, **không đụng
   đến** định dạng / cấu trúc xung quanh.
5. Lưu sang tệp mới.

### Hai chế độ giữ định dạng

#### Mặc định (v0): giữ định dạng cấp đoạn

Toàn bộ runs trong một đoạn được nối lại, dịch cùng lúc, ghi vào run
đầu tiên. Style của run đầu tiên áp dụng cho cả đoạn.

- **Giữ nguyên:** tiêu đề, danh sách, font / căn lề / màu của đoạn,
  cấu trúc bảng, header / footer.
- **Mất:** in đậm / in nghiêng giữa câu (ví dụ "**1.500.000 VNĐ**" lẫn
  trong câu thường).

#### Tuỳ chọn (v1): giữ định dạng cấp run

Bật bằng cờ `preserve_runs=True` (CLI: chưa expose; API: thêm trường
form). Walker đặt placeholder `⟦N⟧` ở mỗi ranh giới run, yêu cầu
translator giữ nguyên placeholder, rồi phân phối lại văn bản đã dịch
vào đúng từng run.

- **Giữ thêm được:** in đậm / in nghiêng / hyperlink **giữa câu**.
- **Yêu cầu:** translator phải bảo toàn placeholder. LLM chất lượng
  cao (Qwen3-8B+, Claude Haiku) làm tốt; LLM nhỏ (1.7B) thường để mất.
- **Tự rơi về v0** khi placeholder bị thiếu / sai thứ tự — tệp đầu
  ra **không bao giờ bị hỏng**.

### Mô hình dịch

Hai backend:

1. **LLM** *(mặc định)* — dùng LLM trò chuyện đã cài (Qwen3 / Gemma /
   Claude / GPT-4). Không tải thêm gì. Chất lượng tỷ lệ với kích thước
   mô hình.
2. **HF chuyên dụng** — `transformers` seq2seq:
   - `google/madlad400-3b-mt` (Apache 2.0) — chuyên dịch 200+ ngôn ngữ.
   - `facebook/m2m100_418M` (MIT) — nhỏ, chạy CPU được.
   Lần đầu tải vài GB; sau đó chạy local.

## Giới hạn đã biết

- **PDF / ảnh** không dịch trực tiếp. Dùng `nom convert` để đổi sang
  `.docx` trước, hoặc xem trang [Chuyển định dạng](./convert.md).
- **Equations và SmartArt** trong `.docx` / `.pptx` đi qua không sửa.
- **Code block trong Markdown** hiện tại bị dịch (sẽ skip ở v0.5).
- **Style công thức Excel** giữ nguyên; nhưng tham chiếu chéo sheet
  có dấu cách (`='Sheet 1'!A1`) chưa được kiểm tra kỹ — báo lại nếu
  thấy hỏng.
- **Tốc độ phụ thuộc backend.** LLM cục bộ ~0.5–2 s/đoạn; mô hình HF
  chuyên dụng ~0.7–1 s/đoạn trên CPU, nhanh gấp 5–10 lần trên GPU.

## Thống kê chất lượng

Đã đo trên OPUS-100 (300 cặp ngẫu nhiên, RTX 3090, fp16):

| Mô hình | Hướng | chrF | BLEU | Diacritic recall | Độ trễ p50 |
| --- | --- | --- | --- | --- | --- |
| `m2m100_418M` | EN → VN | 35.73 | 16.33 | **53.06 %** | 870 ms |
| `m2m100_418M` | VN → EN | 38.63 | 20.64 | n/a | 696 ms |

Cảnh báo: m2m100 có **tỷ lệ giữ dấu thấp** ở chiều EN → VN (chỉ 53 %).
Không dùng làm mặc định cho giấy tờ chính thức. MADLAD-3B đang chạy
benchmark, sẽ cập nhật.

Ghi nhận đầy đủ ở [`benchmarks/results/`](../../benchmarks/results/).

## Liên quan

- [Chuyển định dạng](./convert.md) — PDF / ảnh → DOCX.
- [Khôi phục dấu](./diacritic-restoration.md) — bù dấu tiếng Việt.
