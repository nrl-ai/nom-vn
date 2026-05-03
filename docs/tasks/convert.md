# Chuyển định dạng

Chuyển PDF và ảnh thành tệp `.docx` có thể chỉnh sửa — bước trung
gian trước khi dịch hoặc trích xuất nội dung. OCR nội bộ qua Tesseract
nên không cần dịch vụ ngoài, an toàn cho tài liệu nhạy cảm.

## Định dạng được hỗ trợ

| Đầu vào | Đầu ra | Cách xử lý |
| --- | --- | --- |
| `.pdf` (có lớp văn bản) | `.docx` | Trích xuất trực tiếp qua `pdfplumber` |
| `.pdf` (bản quét, không có lớp văn bản) | `.docx` | Hiển thị từng trang thành ảnh rồi OCR bằng Tesseract |
| `.pdf` lai (vừa có vừa không) | `.docx` | Tự động chọn theo từng trang |
| `.png`, `.jpg`, `.jpeg` | `.docx` | OCR qua Tesseract |
| `.tif`, `.tiff` | `.docx` | OCR qua Tesseract |
| `.bmp`, `.webp` | `.docx` | OCR qua Tesseract |

PDF lai (ví dụ tài liệu vừa có chữ thường vừa có biểu mẫu quét) được
xử lý theo từng trang: trang nào trích xuất được trên 32 ký tự thì
dùng lớp văn bản, dưới ngưỡng đó thì rơi sang OCR.

## Cách dùng

### Trong giao diện web

(Tab giao diện cho `Chuyển định dạng` đang được phát triển. Tạm thời
dùng dòng lệnh hoặc gọi trực tiếp qua API.)

### Dòng lệnh

```bash
# Mặc định: nhận diện cả tiếng Việt và tiếng Anh, ghi cùng thư mục
nom convert hop-dong.pdf
# → tạo hop-dong.docx

# Chỉ định ngôn ngữ OCR (mã Tesseract: vie, eng, ...)
nom convert scan.png --ocr-language vie

# Đặt tên tệp đầu ra
nom convert form.pdf --output form-extracted.docx
```

### Gọi trực tiếp qua API HTTP

```bash
curl -X POST http://localhost:8080/api/tools/convert/file \
  -F "file=@invoice.pdf" \
  -F "ocr_language=vie+eng" \
  -o invoice.docx
```

Phản hồi trả về thẳng tệp `.docx`; thống kê (số trang trích xuất / số
trang phải OCR / tổng ký tự) nằm trong tiêu đề HTTP `X-Convert-Stats`.

## Cách hoạt động

Đối với PDF, mỗi trang được xử lý độc lập:

1. **Bước 1 — Thử trích xuất lớp văn bản.** Dùng `pdfplumber` để rút
   chữ trực tiếp từ siêu dữ liệu PDF. Nhanh, chính xác cao, không sai
   chính tả.
2. **Bước 2 — Phán đoán có cần OCR không.** Nếu trang đó cho ra ít
   hơn 32 ký tự, có nghĩa là trang đó là ảnh quét — chuyển sang OCR.
3. **Bước 3 — OCR khi cần.** Hiển thị trang đó thành ảnh độ phân
   giải 220 DPI qua `pypdfium2`, rồi đưa qua Tesseract với gói ngôn
   ngữ đã chỉ định.
4. **Bước 4 — Ghi `.docx`.** Mỗi trang nguồn → một nhóm đoạn văn bản
   trong tệp đầu ra, ngăn cách bằng ngắt trang cứng để giữ ranh giới
   trang gốc.

## Kết hợp với dịch thuật

Hai bước thường đi với nhau: **chuyển → dịch**:

```bash
# 1. Đổi PDF → DOCX
nom convert hop-dong.pdf
# → hop-dong.docx

# 2. Dịch DOCX
nom translate hop-dong.docx --src vi --tgt en
# → hop-dong.en.docx
```

Hoặc viết trong Python:

```python
from nom.convert import convert_to_docx
from nom.translate import LLMTranslator
from nom.translate.formats import translate_docx
from nom.llm import Ollama

llm = Ollama(model="qwen3:8b", think=False)
translator = LLMTranslator(llm=llm, source_lang="vi", target_lang="en")

convert_to_docx("scan.pdf", "scan.docx", ocr_language="vie+eng")
translate_docx("scan.docx", "scan.en.docx", translator)
```

## Số đo nội bộ — v0.4 (2026-05-03)

Đo trên kho đánh giá
[`nrl-ai/vn-ocr-documents-eval`](https://huggingface.co/datasets/nrl-ai/vn-ocr-documents-eval)
v0.4: **156 tài liệu** trên 8 cấu hình, chia thành hai nhóm chính —
**ảnh quét thật** từ `chinhphu.vn` + `hanoi.gov.vn` (9 tài liệu,
ground truth do người đọc xác minh trực tiếp) và **ảnh quét tổng
hợp** rendered từ văn bản tiếng Việt công khai (UDHR, wiki_vi,
tatoeba, wikisource Truyện Kiều) cộng các mẫu hoá đơn / hợp đồng /
đơn từ tham số hoá, áp dụng pipeline 8 bước hiệu ứng máy quét
(skew, vignette, hơi vàng giấy, nhiễu hạt, banding máy quét, blur,
viền tối, JPEG round-trip).

| Cấu hình | n | Nguồn | CER trung bình (chuẩn hoá khoảng trắng) |
|---|---:|---|---:|
| `real` | 9 | chinhphu.vn + hanoi.gov.vn (ảnh quét đã ký) | **12,62 %** |
| `formal` | 24 | UDHR-vie + hiệu ứng quét | ~9 % |
| `news_business` | 24 | wiki_vi + hiệu ứng quét | ~7 % |
| `conversational` | 24 | tatoeba + hiệu ứng quét | ~6 % |
| `literary` | 14 | Wikisource Truyện Kiều + hiệu ứng quét | ~10 % |
| `receipt` | 21 | 7 mẫu × 3 seed (hoá đơn, biên lai, phiếu chi, vé máy bay, ủng hộ, điện nước, viện phí) | ~3 % |
| `contract` | 20 | 5 mẫu × 4 seed (lao động, thuê nhà, kinh tế, dịch vụ, vay) | ~3 % |
| `form` | 20 | 5 mẫu × 4 seed (nghỉ việc, xác nhận cư trú, nhập học, nghỉ phép, đăng ký kinh doanh) | ~3 % |
| **Tổng** | **156** | | **mean 6,66 %, median 4,32 %** |

Throughput: ~1,3 giây / tài liệu trên CPU đơn lõi (Intel i7-13700H).
CER tính sau khi chuẩn hoá NFC + gộp các chuỗi khoảng trắng thành
một dấu cách.

**Cảm nhận về độ khó**: ảnh quét thật (cấu hình `real`) **khó hơn
~13 lần** so với ảnh tổng hợp do có dấu mộc đỏ, chữ ký tay, hơi
nhoè, watermark mờ ở nền và các từ viết tắt hành chính
("KT.", "Lưu: VT") mà gói `vie` của Tesseract không xử lý tốt.

JSON kết quả + ma trận tính năng đầu cuối:
[`benchmarks/results/baseline_features_e2e_v4.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_features_e2e_v4.json).

Tái lập từ một bản clone sạch:

```bash
pip install -e ".[doc]"
python benchmarks/data/vn_documents_ocr_v2/_synth_corpus.py
python benchmarks/accuracy/bench_features_e2e.py
```

**Cảnh báo phương pháp:**

- 9 ảnh quét thật vẫn là tập nhỏ; mở rộng lên 20+ cần chú thích thủ
  công thêm 11 tài liệu nữa (tốc độ ~10 phút mỗi trang).
- 147 tài liệu tổng hợp dùng văn bản gốc làm ground truth hoàn hảo,
  đánh đổi: chữ in DejaVuSans + hiệu ứng quét **không có cấu trúc
  thư hành chính đầy đủ** (mộc, chữ ký, ô đóng dấu) như bản quét
  thật. Phù hợp cho đo nhận dạng ký tự cấp dòng, không thay thế
  được kho ảnh quét gốc.
- Phân loại thực thể trên kho v0.4: **102 LAW_REF, 203 DATE, 89
  MONEY, 59 PHONE_VN, 39 ID_VN** — bản v0.3 chưa có ID_VN nào
  vì chưa có hợp đồng / đơn từ chứa CCCD.

## Yêu cầu hệ thống

- **Tesseract** đã cài đặt cùng các gói ngôn ngữ cần dùng:
  ```bash
  sudo apt install tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng
  ```
  hoặc tương đương trên macOS / Windows.
- **Python deps:** `pdfplumber`, `pypdfium2`, `pytesseract`,
  `python-docx`, `Pillow`. Tất cả đều nằm trong gói `nom-vn[doc]`:
  ```bash
  pip install -e ".[doc]"
  ```

## Giới hạn đã biết

- **Không giữ nguyên bố cục theo điểm ảnh.** Văn bản trích xuất là
  văn bản dạng dòng chảy — PDF nhiều cột có thể bị xen kẽ. Nếu cần
  giữ chính xác bố cục, đây không phải công cụ phù hợp.
- **Bảng phức tạp** trong PDF có thể không giữ đúng ranh giới — chữ
  trong bảng vẫn được trích nhưng nằm dạng đoạn văn liền nhau.
- **Hình ảnh và biểu đồ** không được chuyển sang `.docx` — chỉ chữ.
- **Chất lượng OCR phụ thuộc độ phân giải nguồn.** Bản scan dưới 200
  DPI sẽ ra kết quả rất kém. Nếu sai chính tả nhiều, cân nhắc bước
  hậu xử lý qua [Khôi phục dấu](./diacritic-restoration.md).
- **Tốc độ:** trang OCR mất khoảng 2–5 giây trên CPU; trang có lớp
  văn bản gần như tức thì.

## Liên quan

- [Dịch thuật](./translate.md) — bước tiếp theo sau khi chuyển sang
  `.docx`.
- [Khôi phục dấu](./diacritic-restoration.md) — sửa kết quả OCR mất
  dấu tiếng Việt.
