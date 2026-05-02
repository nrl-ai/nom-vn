# Dịch thuật

Dịch văn bản và **giữ nguyên định dạng** giữa tiếng Việt và tiếng Anh.
Toàn bộ chạy trên máy người dùng — an toàn cho tài liệu nhạy cảm như
hợp đồng, báo cáo nội bộ, hồ sơ y tế.

## Định dạng được hỗ trợ

| Loại tệp | Trạng thái | Ghi chú |
| --- | --- | --- |
| `.docx` | Đầy đủ | Tiêu đề, danh sách, bảng, đầu trang / chân trang, liên kết |
| `.xlsx` | Đầy đủ | Mọi ô chữ đều dịch; số, công thức, định dạng giữ nguyên |
| `.pptx` | Đầy đủ | Trang trình chiếu, ô bảng, ghi chú thuyết trình, nhóm hình lồng nhau |
| `.txt`, `.md`, `.rst` | Đầy đủ | Tách theo đoạn (dòng trắng); giữ nguyên tiêu đề Markdown |
| `.pdf`, ảnh | Qua bước chuyển đổi | Đổi sang `.docx` rồi dịch lại — xem [Chuyển định dạng](./convert.md) |

## Cách dùng

### Trong giao diện web

Mở mục **Dịch thuật** ở thanh điều hướng bên trái.

- **Văn bản** — dán đoạn cần dịch, chọn chiều (Việt ↔ Anh), bấm Dịch.
- **Tệp** — kéo thả tệp `.docx` / `.xlsx` / `.pptx` / `.txt` / `.md` /
  `.rst` vào khu thả. Tệp dịch tự động tải về với tên
  `<gốc>.<mã-ngôn-ngữ>.<đuôi-tệp>`.

### Dòng lệnh

```bash
# Mặc định: tiếng Việt → tiếng Anh, dùng LLM cài sẵn (qwen3:8b)
nom translate hop-dong.docx

# Đổi chiều, chỉ định mô hình chuyên dụng từ HuggingFace
nom translate report.xlsx --src en --tgt vi \
    --backend hf --model google/madlad400-3b-mt

# Đặt tên tệp đầu ra cụ thể
nom translate slides.pptx --output slides_vi.pptx
```

### Gọi trực tiếp qua API HTTP

```bash
# Một đoạn ngắn
curl -X POST http://localhost:8080/api/tools/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hợp đồng vô hiệu", "source": "vi", "target": "en"}'

# Cả tệp
curl -X POST http://localhost:8080/api/tools/translate/file \
  -F "file=@contract.docx" \
  -F "source=vi" -F "target=en" \
  -o contract_en.docx
```

Phản hồi trả về thẳng tệp đã dịch; thống kê (số đoạn dịch / bỏ qua /
lỗi, số ký tự vào / ra) nằm trong tiêu đề HTTP `X-Translation-Stats`.

## Cách hoạt động

Cách giữ định dạng dùng **bộ duyệt theo cấu trúc tệp**, không đi qua
định dạng trung gian — đơn giản hơn và đủ tốt cho khoảng 95 % trường
hợp:

1. Mở tệp bằng thư viện gốc (`python-docx`, `openpyxl`, `python-pptx`).
2. Duyệt cây cấu trúc — đoạn văn, ô bảng, hình khối, trang trình chiếu.
3. Mỗi đơn vị văn bản → gọi `Translator` (LLM trò chuyện hoặc mô hình
   chuyên dụng).
4. Ghi văn bản đã dịch ngược trở lại đúng vị trí gốc, **không đụng
   đến** định dạng / cấu trúc xung quanh.
5. Lưu sang tệp mới.

### Hai mức độ giữ định dạng

#### Mức mặc định: giữ định dạng cấp đoạn

Toàn bộ các đoạn ký tự nhỏ (`run` trong `.docx`) bên trong cùng một
đoạn văn được nối lại, dịch một lượt, rồi viết vào đoạn ký tự đầu
tiên. Kiểu chữ của đoạn ký tự đầu tiên áp dụng cho cả đoạn văn sau
khi dịch.

- **Giữ nguyên:** tiêu đề, danh sách, kiểu chữ / căn lề / màu của cả
  đoạn, cấu trúc bảng, đầu trang / chân trang.
- **Mất:** in đậm / in nghiêng / liên kết nằm giữa câu (ví dụ
  "**1.500.000 VNĐ**" lẫn trong câu thường) — kiểu chữ này gộp về
  kiểu của đoạn ký tự đầu tiên.

#### Mức nâng cao: giữ định dạng cấp đoạn ký tự

Bật bằng cờ `preserve_runs=True` (giao diện web: chưa hiển thị; gọi
API: thêm trường form). Bộ duyệt đặt ký hiệu giữ chỗ `⟦N⟧` ở mỗi ranh
giới giữa các đoạn ký tự, yêu cầu mô hình giữ nguyên các ký hiệu này,
sau đó phân phối lại văn bản đã dịch về đúng từng đoạn ký tự.

- **Giữ thêm được:** in đậm / in nghiêng / liên kết **nằm giữa câu**.
- **Yêu cầu:** mô hình phải bảo toàn các ký hiệu giữ chỗ. Mô hình lớn
  (Qwen3-8B trở lên, Claude Haiku) làm tốt việc này; mô hình rất nhỏ
  (1.7B trở xuống) thường để mất.
- **Tự lùi về mức mặc định** khi ký hiệu giữ chỗ bị thiếu hoặc đảo
  thứ tự — tệp đầu ra **không bao giờ bị hỏng**.

### Hai cách dịch (chọn ở mục "Cách dịch" trong giao diện)

1. **LLM** *(mặc định)* — dùng LLM trò chuyện đã cài sẵn (Qwen3 /
   Gemma / Claude / GPT-4). Không cần tải thêm. Chất lượng tỉ lệ với
   kích thước mô hình.
2. **Chuyên dụng** — mô hình dịch riêng từ HuggingFace:
   - `google/madlad400-3b-mt` (Apache 2.0) — chuyên dịch hơn 200 ngôn
     ngữ.
   - `facebook/m2m100_418M` (MIT) — nhỏ, có thể chạy trên CPU.

   Lần đầu tải vài GB; sau đó chạy hoàn toàn trên máy.

## Giới hạn đã biết

- **PDF và ảnh** không dịch trực tiếp — phải đổi sang `.docx` trước
  bằng `nom convert`. Xem [Chuyển định dạng](./convert.md).
- **Công thức toán và SmartArt** trong `.docx` / `.pptx` đi qua không
  bị thay đổi (cũng không được dịch).
- **Khối mã trong Markdown** hiện đang bị dịch — sẽ bỏ qua ở phiên
  bản tiếp theo.
- **Tham chiếu chéo Sheet trong `.xlsx`** giữ nguyên với tên Sheet
  đơn giản; tham chiếu có dấu cách (`='Sheet 1'!A1`) chưa được kiểm
  tra kỹ — báo lại nếu thấy lỗi.
- **Tốc độ tuỳ thuộc cách dịch.** LLM cục bộ trung bình 0.5–2 giây
  mỗi đoạn; mô hình chuyên dụng 0.7–1 giây trên CPU, nhanh hơn 5–10
  lần khi có GPU.

## Số đo chất lượng đã đo

Đo trên OPUS-100 (300 cặp ngẫu nhiên, RTX 3090, độ chính xác fp16):

| Mô hình | Chiều dịch | chrF | BLEU | Tỉ lệ giữ dấu | Trễ trung vị |
| --- | --- | --- | --- | --- | --- |
| `m2m100_418M` | EN → VN | 35.73 | 16.33 | **53.06 %** | 870 ms |
| `m2m100_418M` | VN → EN | 38.63 | 20.64 | (không đo) | 696 ms |

Cảnh báo: ở chiều EN → VN, `m2m100` chỉ giữ được khoảng một nửa số
dấu tiếng Việt. **Không nên dùng làm mặc định** cho giấy tờ chính
thức. Chúng tôi đang đo `MADLAD-3B` (kích thước 3B, chuyên dụng) và
sẽ cập nhật.

Số đo đầy đủ đã lưu ở [`benchmarks/results/`](../../benchmarks/results/).

## Liên quan

- [Chuyển định dạng](./convert.md) — đưa PDF / ảnh về `.docx`.
- [Khôi phục dấu](./diacritic-restoration.md) — bù dấu cho tiếng Việt
  không dấu.
