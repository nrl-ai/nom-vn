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
| `telex_real_25.jsonl` | Lỗi keystroke Telex/VNI thực | 25 | Còn sót `s`/`f`/`r`/`x`/`j`/`w`/`a`/`e`/`o` do thoát thiếu |
| `ocr_25.jsonl` | Output Tesseract / EasyOCR trên ảnh quét VN | 25 | Lỗi engine-specific (`m`↔`rn`, `cl`↔`d`, `0`↔`o`) |
| `legal_real_25.jsonl` | Văn bản pháp lý VN bị strip-dấu | 25 | Từ vựng register trang trọng (căn cứ, điều, khoản), tên riêng |
| `news_real_25.jsonl` | Tiêu đề + thân tin tức VN bị strip-dấu | 25 | Tiếng Việt trang trọng hiện đại, địa danh, từ vựng thời sự |

**Tổng: 150 câu.** Sáu register khác nhau bao quát phạm vi nguồn lỗi
thực tế mà mô hình triển khai sẽ gặp. Mỗi cặp được đối chiếu thủ công
với một ví dụ nhiễu thật.

## Lưu ý trung thực

- **150 câu vẫn ở vùng nhiễu thống kê.** Mỗi slice 25 câu cho khoảng
  tin cậy 95 % rộng ±9 pp; khoảng tin cậy 95 % cho tổng hợp 150 câu là
  ±5 pp. Coi đây là smell-test định hướng, không phải bảng xếp hạng.
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
