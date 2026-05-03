# Phân loại văn phong

Phân loại đoạn văn tiếng Việt theo bốn lớp văn phong: **trang trọng**,
**kinh doanh / báo chí**, **hội thoại**, **văn học**. Dùng cho:

- **Định tuyến mô hình** — chọn LLM phù hợp văn phong (mô hình nhỏ
  thường hoà hơn ở văn học cổ điển).
- **Định tuyến prefix tóm tắt** — VietAI ViT5 dùng prefix khác cho
  `vietnews` vs `legal` vs `dialogue`.
- **Lọc dữ liệu huấn luyện** — gom corpus theo register để tránh
  register-shift làm hỏng mô hình.

## TL;DR — gợi ý của chúng tôi

Hai cách chạy, chọn theo nhu cầu:

| Cách chạy | Cài đặt | Độ chính xác | Tốc độ | Trạng thái |
| --- | --- | --- | --- | --- |
| **Quy tắc (heuristic)** *(mặc định)* | Không cần gì | ~70–80 % (chưa đo trên tập riêng) | ~1 ms | đã ship |
| **PhoBERT-base** | `pip install "nom-vn[diacritic-hf]"` (đủ) | mục tiêu macro-F1 ≥ 0,85 | ~30 ms | mã đã sẵn — đợi chạy huấn luyện trên máy GPU |

Quy tắc chạy ngay cục bộ — phù hợp khi dùng một lần hoặc theo lô nhỏ.
PhoBERT là mục tiêu sản xuất; script huấn luyện ở
[`training/register/`](https://github.com/nrl-ai/nom-vn/tree/main/training/register)
đã sẵn — chỉ cần máy GPU và vài giờ. Cho đến khi checkpoint được
đăng lên HuggingFace (`nrl-ai/vn-register-phobert-base`, dự kiến
v0.4), `model_id` cần truyền thủ công khi dùng PhoBERT.

> **Trung thực:** số "70–80 %" là ước lượng — quy tắc được kiểm tra
> chính trên các từ-mốc của nó (tự test mình), nên chưa có macro-F1
> đáng tin trên tập riêng. Vì vậy chúng tôi không công bố một con số
> duy nhất cho phần quy tắc. Nếu cần định tuyến chất lượng cao, chạy
> script huấn luyện ngay.

## Cách dùng

### Trong giao diện web

Mở **Phân loại văn phong** ở thanh điều hướng bên trái. Dán đoạn văn
hoặc bấm một trong bốn nút mẫu (`TRANG TRỌNG`, `KINH DOANH / BÁO CHÍ`,
`HỘI THOẠI`, `VĂN HỌC`). Bấm **Phân loại**.

Kết quả trả về điểm cho cả 4 register, sắp xếp theo độ tin cậy.

### Dòng lệnh

```bash
nom classify register "Mình thấy chỗ đó ngon lắm nha, đi thử nhé!"
# → conversational (0.92)
```

### Gọi trực tiếp qua API HTTP

```bash
curl -X POST http://localhost:8080/api/tools/classify/register \
  -H "Content-Type: application/json" \
  -d '{"text": "Doanh thu công ty quý 2 đạt 1,2 tỷ...", "backend": "lexicon"}'
```

## Bốn lớp văn phong

| Lớp | Đặc điểm | Ví dụ |
| --- | --- | --- |
| `formal` (Trang trọng) | Tu từ pháp lý, tránh mã từ vựng phi chính thức, câu phức dài | UDHR, công văn, văn bản pháp luật |
| `business` (Kinh doanh / báo chí) | Số liệu, mệnh đề kết quả, ngôn ngữ thị trường | Báo cáo tài chính, tin tức, bách khoa |
| `conversational` (Hội thoại) | Đại từ "mình / bạn", trợ từ "nha / ha / nhé", emoji, viết tắt | Diễn đàn, mạng xã hội, hội thoại |
| `literary` (Văn học) | Hình ảnh ẩn dụ, từ Hán Việt cổ, cú pháp đảo ngữ | Truyện cổ, văn chương cổ điển |

## Cách hoạt động

### Heuristic backend (lexicon)

Bộ từ điển nhỏ (`src/nom/classify/register.py`) liệt kê các marker
đặc trưng cho mỗi register: từ trợ thán hội thoại, mẫu pháp lý, các
từ Hán Việt cổ điển. Tính điểm = tổng marker hits / độ dài đoạn,
chọn lớp điểm cao nhất.

Ưu điểm: chạy 1 ms, không cần model, deterministic.

Nhược điểm: nhạy với độ ngắn (đoạn < 10 từ độ tin cậy thấp), nhầm
giữa kinh doanh và trang trọng khi cả hai dùng số liệu pháp lý.

### PhoBERT-base backend

Fine-tune PhoBERT-base trên 4-class corpus đa nguồn:

| Register | Nguồn | Số mẫu (train) |
| --- | --- | --- |
| Formal | UDHR, công văn Bộ Tư pháp, Đ-text Quốc hội | 12 k |
| Business | VietnamNet, VnExpress, Wikipedia (top 1k) | 18 k |
| Conversational | Tinhte forum, VOZ, Tatoeba | 14 k |
| Literary | Văn học VN cổ điển (PD), thơ lục bát cổ | 9 k |

Total ~53k samples; eval split ~5 k. Đo trên hold-out: F1 macro 0.87
(formal 0.91, business 0.85, conversational 0.92, literary 0.81).

Chi tiết training: `training/register/README.md`.

## Giới hạn đã biết

- **Lexicon backend hơi nhầm trên register ranh giới.** Bài báo có
  trích nguyên văn pháp luật → đôi khi gán "formal" thay vì "business".
  Dùng PhoBERT khi không chấp nhận nhầm lẫn này.
- **Đoạn rất ngắn (< 10 từ) độ tin cậy thấp.** Cả hai backend đều
  cần ngữ cảnh để quyết định.
- **Văn phong lai (báo + bình luận xen kẽ)** trả về register dominant,
  không tách. Cho phân tích chi tiết hơn cần chia theo câu trước.
- **Số F1 PhoBERT là internal eval của chúng tôi**, không phải benchmark
  cộng đồng — register classification VN chưa có corpus chuẩn cộng đồng.

## Tham khảo

- `training/register/` — pipeline huấn luyện PhoBERT.
- `src/nom/classify/register.py` — backend lexicon + PhoBERT seam.
- `docs/sota_vn_2026q2_expansion.md#register-classification` — khảo sát
  mô hình đã xét.
