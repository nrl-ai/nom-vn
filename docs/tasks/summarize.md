# Tóm tắt văn bản

Cô đọng đoạn văn dài về tin tức, hợp đồng, hội thoại — giữ nguyên ý
chính, lược bỏ chi tiết phụ. Chạy hoàn toàn trên máy người dùng.

## TL;DR — gợi ý của chúng tôi

`pip install "nom-vn[summarize]"` để có sẵn `transformers` + `torch`.
Mặc định dùng `VietAI/vit5-large-vietnews` (Apache 2.0, 866 M tham
số) — ROUGE-1 63.4 trên `vietnews`. Lần đầu tải khoảng 3.3 GB; sau
đó chạy hoàn toàn cục bộ.

## Cách dùng

### Trong giao diện web

Mở **Tóm tắt** ở thanh điều hướng bên trái. Dán đoạn văn (giới hạn
~1024 token, vượt sẽ tự cắt), chọn:

- **Văn phong** — Báo / tin tức (mặc định, dùng tiền tố `vietnews`),
  Hợp đồng (tiền tố `legal`), Hội thoại (tiền tố `dialogue`). Tiền
  tố giúp mô hình điều chỉnh giọng văn đầu ra.
- **Độ dài tóm tắt** — Ngắn (~64 token), Vừa (~128 token), Dài
  (~256 token, mặc định).

Bấm **Tóm tắt** (hoặc ⌘/Ctrl + Enter). Lần đầu mất 30–60 giây để tải
mô hình; lần sau chỉ vài giây.

### Dòng lệnh

```bash
nom summarize "Theo công bố của Tổng cục Thống kê, GDP quý I tăng 5,66%..."

# Đổi văn phong + độ dài
nom summarize hop_dong.txt --register legal --max-tokens 128
```

### Gọi trực tiếp qua API HTTP

```bash
curl -X POST http://localhost:8080/api/tools/nlp/summarize \
  -H "Content-Type: application/json" \
  -d '{"text": "...", "register": "vietnews", "max_tokens": 256}'
```

## Cách hoạt động

`nom.summarize` là wrapper mỏng quanh `transformers`:

1. **Tách token** — `vit5-large-vietnews` dùng SentencePiece âm tiết
   tiếng Việt. Giới hạn đầu vào ở 1024 token.
2. **Chèn tiền tố** — `vietnews:`, `legal:`, hoặc `dialogue:` trước
   đầu vào để chỉ định văn phong.
3. **Sinh** — tìm chùm 4 nhánh (beam=4), `length_penalty=2.0`,
   `no_repeat_ngram_size=3`.
4. **Giải mã** — bỏ token đặc biệt, chuẩn hoá NFC, trả về.

Truyền cả tài liệu, không cắt theo câu — mô hình tự cô đọng cấu trúc
diễn ngôn (đoạn mở, thân, kết).

## Giới hạn đã biết

- **Giới hạn 1024 token đầu vào.** Bài dài hơn thì cắt thẳng —
  v0 chưa có cơ chế cắt-và-ghép. Với hợp đồng dài cần chia đoạn
  thủ công.
- **Tóm tắt rút trích, không tổng hợp.** Mô hình chọn cụm câu
  trong bài rồi nén lại — không phát sinh ý mới hoặc viết lại
  mạnh. Nếu cần tóm tắt giọng tự nhiên hơn, đổi sang LLM trò
  chuyện qua `nom.chat` với prompt phù hợp.
- **Bịa số liệu.** Đo nội bộ
  ([JSON kết quả](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/accuracy/summarize_wiki_vi_baseline.json),
  n=10 trên `wiki_vi`): **1 trong 10 mẫu thêm năm "2025" không có
  trong đầu vào** (bài về TP.HCM). Một mẫu khác (đoạn 234 ký tự
  về Việt Nam), mô hình tự bịa ra con số GDP "6,8 % – 7,0 %" không
  có trong nguồn. **Đừng dùng cho tóm tắt pháp lý / tài chính**
  mà không kiểm chứng từng số — n nhỏ nên đây là cảnh báo định
  hướng, không phải đo định lượng đầy đủ.
- **Ngôn ngữ.** Chỉ tiếng Việt; văn bản tiếng Anh sẽ được mô hình cố
  dịch thô — không khuyến nghị.

## Mô hình thay thế

| Mô hình | License | Khi nào chọn |
| --- | --- | --- |
| `VietAI/vit5-large-vietnews` *(mặc định)* | Apache 2.0 | Tin tức / báo chí |
| `VietAI/vit5-base-vietnews` | Apache 2.0 | Máy 4 GB RAM, độ chính xác giảm ~3 ROUGE |
| LLM trò chuyện qua `nom.chat` | tuỳ | Cần kiểm soát phong cách / tóm tắt theo yêu cầu prompt cụ thể |

## Liên quan

- [Phân loại văn phong](./register.md) — tự động chọn prefix phù hợp.
- [Khôi phục dấu](./diacritic-restoration.md) — chạy trước nếu đầu
  vào thiếu dấu (đầu vào thiếu dấu làm bộ tóm tắt giảm chất lượng).
