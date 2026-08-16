# Bộ eval thực tế cho sửa chính tả tiếng Việt (OOD)

Các cặp `(noisy, clean)` được hand-curate, trong đó mẫu nhiễu lấy từ
**nguồn lỗi tiếng Việt thực tế**, KHÔNG phải từ `nom.text.noise`. Dùng
như tập bổ sung ngoài-phân-phối (out-of-distribution) cho lưới synthetic
ở `benchmarks/data/spell_correction_eval/`.

Eval synthetic đo mức độ mô hình đảo ngược chính bộ sinh nhiễu của chúng
tôi. Eval này đo xem mô hình có xử lý được những lỗi mà bộ sinh không
mô hình hoá (hoặc mô hình hoá khác phân phối):

| Slice | Nguồn nhiễu | Số câu | Đo cái gì |
|---|---|---:|---|
| `forum_25.jsonl` | Forum / mạng xã hội tiếng Việt | 25 | Viết tắt teen-code, dấu thiếu, dấu câu thoải mái |
| `mobile_25.jsonl` | Lỗi autocorrect của bàn phím điện thoại | 25 | Thay từ sai, lỗi phím gần, sai cấp viết hoa |
| `ocr_25.jsonl` | Output Tesseract / EasyOCR trên ảnh quét VN | 25 | Lỗi engine-specific (`m`↔`rn`, `cl`↔`d`, `0`↔`o`) |
| `legal_real_25.jsonl` | Văn bản pháp lý VN bị strip-dấu | 25 | Từ vựng register trang trọng (căn cứ, điều, khoản), tên riêng |
| `news_real_25.jsonl` | Tiêu đề + thân tin tức VN bị strip-dấu | 25 | Tiếng Việt trang trọng hiện đại, địa danh, từ vựng thời sự |
| `furniture_50.jsonl` | Văn bản hành chính VN thật (chinhphu.vn, hanoi.gov.vn) | 50 | Tiêu ngữ, tiêu đề viết hoa, nhãn biểu mẫu, khối chữ ký |

**Tổng: 175 câu.** Sáu lát cắt bao quát phạm vi nguồn lỗi thực tế mà
mô hình triển khai sẽ gặp.

## `telex_real_25` đã bị loại bỏ (2026-08-16)

Lát cắt này từng có 25 câu, mỗi câu là một chuỗi Telex thô cho **toàn
bộ câu**, như thể bộ gõ tắt hẳn mà người dùng vẫn tiếp tục gõ chữ dấu:

```
Toi yeeu Vieejt Nam vaf daats nuwowcs nayf tuyeejt vowif
```

Người dùng thật không tạo ra lỗi kiểu đó. Khi bộ gõ tắt, màn hình hiện
ra chuỗi vô nghĩa ngay từ chữ thứ hai; người dùng hoặc bật lại bộ gõ,
hoặc chuyển sang gõ tiếng Việt không dấu (`Toi yeu Viet Nam`) — trường
hợp sau đã được `legal_real_25` và `news_real_25` bao phủ.

Nhiều nhãn gold trong lát cắt cũng sai: `coos` giải mã thành `cố` nhưng
được gán nhãn `được`; `chowj` giải mã thành `chợ` nhưng gán nhãn `chưa`;
`ngeexn` giải mã thành `ngẽn` nhưng gán nhãn `nên`. Có cặp lệch số token
giữa đầu vào và nhãn, và vài nhãn không phải tiếng Việt trôi chảy
(`chú ý đọc liệu bản tường trình`). Mô hình bị trừ điểm vì không tái tạo
được nhãn hỏng, kéo tổng hợp của chính chúng tôi xuống khoảng 8,7 pp
trên một phép đo không có ý nghĩa.

Lỗi Telex là có thật, nhưng **cục bộ**: một hai âm tiết không kết hợp
được trong khi phần còn lại của câu vẫn đúng. Vì vậy nó thuộc về nhóm
lỗi trộn lẫn trong các register khác — đúng như `nom.text.noise` làm
với dữ liệu huấn luyện — chứ không phải một hạng mục riêng nơi mọi từ
đều hỏng.

## Lưu ý trung thực

- **175 câu vẫn ở vùng nhiễu thống kê.** Mỗi lát cắt 25 câu cho khoảng
  tin cậy 95 % rộng ±9 pp; khoảng tin cậy 95 % cho tổng hợp 175 câu là
  khoảng ±3,5 pp. Coi đây là smell-test định hướng, không phải bảng xếp
  hạng — khoảng tin cậy của chúng tôi và của Toshiiiii1 vẫn chồng lấn.
- **Không ghi chú nguồn theo từng dòng.** Nhiều câu là tổ hợp các mẫu
  quan sát qua nhiều bài/ảnh quét — sao chép verbatim sẽ rò PII hoặc
  vi phạm ToS nền tảng nguồn. Mẫu cấu trúc (ký tự nào đảo, viết tắt
  nào dùng) là thật; nội dung câu xung quanh được paraphrase từ văn
  bản VN công khai.
- **Tiếng lóng forum nhanh cũ.** `vcl` hôm nay có thể là cổ ngữ ngày
  mai. Nên re-curate mỗi 12-18 tháng.

## Tái lập

Bộ eval này được con người curate, không sinh tự động. Để re-bench:

```bash
python benchmarks/accuracy/bench_spell_correction_real.py \
    nrl-ai/vn-spell-correction-base \
    --json benchmarks/results/baseline_real_spell_correction_base.json
```
