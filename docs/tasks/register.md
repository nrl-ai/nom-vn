# Phân loại văn phong

Phân loại đoạn văn tiếng Việt theo bốn lớp văn phong: **trang trọng**,
**kinh doanh / báo chí**, **hội thoại**, **văn học**. Dùng cho:

- **Định tuyến mô hình** — chọn LLM phù hợp văn phong (mô hình nhỏ
  thường hoà hơn ở văn học cổ điển).
- **Định tuyến prefix tóm tắt** — VietAI ViT5 dùng prefix khác cho
  `vietnews` vs `legal` vs `dialogue`.
- **Lọc dữ liệu huấn luyện** — gom kho ngữ liệu theo văn phong để
  tránh hiện tượng dịch chuyển văn phong làm hỏng mô hình.

## TL;DR — gợi ý của chúng tôi

Hai cách chạy, chọn theo nhu cầu:

| Cách chạy | Cài đặt | Độ chính xác | Tốc độ | Trạng thái |
| --- | --- | --- | --- | --- |
| **Quy tắc (heuristic)** *(rẻ tiền)* | Không cần gì | ~70–80 % (chưa đo trên tập riêng) | ~1 ms | đã ship |
| **PhoBERT-base** *(mặc định sản xuất)* | `pip install "nom-vn[diacritic-hf]"` | **macro F1 0,900** trên test n=1234 | ~30 ms | đã ship 2026-05-03 |

Cả hai chạy cục bộ. Quy tắc phù hợp cho phương án dự phòng nhẹ
(không cần GPU, không tải model). PhoBERT là mặc định cho định
tuyến sản xuất —
checkpoint
[`nrl-ai/vn-register-phobert-base`](https://huggingface.co/nrl-ai/vn-register-phobert-base)
(MIT, ~540 MB safetensors) tự động tải lần đầu khi gọi
`PhoBertRegisterClassifier()`.

Số đo nội bộ trên test n=1234 (2026-05-03):

| Class | F1 | Support |
|---|---:|---:|
| `formal` | 0,914 | 34 |
| `business` | 0,906 | 400 |
| `conversational` | 0,915 | 400 |
| `literary` | 0,866 | 400 |
| **macro** | **0,900** | 1234 |

`literary` là lớp yếu nhất — nhầm sang `formal` ~18 % do từ vựng
cổ chia sẻ. Đợt v2 sẽ bổ sung kho văn học VN đa dạng hơn (mở rộng
Wikisource thay vì chỉ Truyện Kiều) trước khi huấn luyện lại.

JSON kết quả:
[`benchmarks/accuracy/register_phobert_base_baseline.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/accuracy/register_phobert_base_baseline.json).
Tái lập:
[`training/register/train.py`](https://github.com/nrl-ai/nom-vn/tree/main/training/register)
(195 giây trên RTX 3090).

## Cách dùng

### Trong giao diện web

Mở **Phân loại văn phong** ở thanh điều hướng bên trái. Dán đoạn văn
hoặc bấm một trong bốn nút mẫu (`TRANG TRỌNG`, `KINH DOANH / BÁO CHÍ`,
`HỘI THOẠI`, `VĂN HỌC`). Bấm **Phân loại**.

Kết quả trả về điểm cho cả 4 lớp văn phong, sắp xếp theo độ tin cậy.

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

### Phương án từ vựng (heuristic)

Bộ từ điển nhỏ (`src/nom/classify/register.py`) liệt kê các từ khóa
đặc trưng cho mỗi văn phong: trợ từ hội thoại, mẫu pháp lý, từ Hán
Việt cổ điển. Tính điểm = tổng số lần khớp / độ dài đoạn, chọn lớp
điểm cao nhất.

Ưu điểm: chạy 1 ms, không cần model, đầu ra ổn định.

Nhược điểm: nhạy với độ ngắn (đoạn < 10 từ độ tin cậy thấp), nhầm
giữa kinh doanh và trang trọng khi cả hai dùng số liệu pháp lý.

### Phương án PhoBERT-base

Tinh chỉnh PhoBERT-base trên kho 4 lớp đa nguồn (mỗi lớp giới hạn
2 000 mẫu, cắt 70/10/20 train/val/test theo lớp):

| Văn phong | Nguồn | Mẫu trong test |
| --- | --- | --- |
| Formal | UDHR-vie, slice `diacritic_eval_v0.txt` | 34 |
| Business | `wiki_vi/articles.jsonl` (CC-BY-SA) | 400 |
| Conversational | `tatoeba_vi` (CC-BY) | 400 |
| Literary | `wikisource_vi` + UD-VTB literary slice | 400 |

Tổng test n=1234. Đo trên hold-out: macro F1 **0,900** (formal 0,914
/ business 0,906 / conversational 0,915 / literary 0,866).

Chi tiết huấn luyện: `training/register/README.md`.

## Giới hạn đã biết

- **Phương án từ vựng dễ nhầm khi văn bản nằm ở ranh giới phong
  cách.** Bài báo có trích nguyên văn pháp luật → đôi khi gán
  "formal" thay vì "business". Dùng PhoBERT khi không chấp nhận
  nhầm lẫn này.
- **Đoạn rất ngắn (< 10 từ) độ tin cậy thấp.** Cả hai phương án
  đều cần ngữ cảnh để quyết định.
- **Văn phong lai (báo + bình luận xen kẽ)** trả về văn phong
  trội, không tách. Cho phân tích chi tiết hơn cần chia theo câu
  trước.
- **Số F1 PhoBERT là đánh giá nội bộ của chúng tôi**, không phải
  bộ kiểm thử chuẩn cộng đồng — phân loại văn phong tiếng Việt
  hiện chưa có kho kiểm thử chuẩn được cộng đồng công nhận.

## Tham khảo

- `training/register/` — pipeline huấn luyện PhoBERT.
- `src/nom/classify/register.py` — phương án từ vựng + chỗ ráp PhoBERT.
- `docs/sota_vn_2026q2_expansion.md#register-classification` — khảo sát
  mô hình đã xét.
