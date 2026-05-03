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

- **Văn phong** — Báo / tin tức (mặc định, dùng prefix `vietnews`),
  Hợp đồng (prefix `legal`), Hội thoại (prefix `dialogue`). Prefix
  giúp mô hình điều chỉnh giọng văn đầu ra.
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

1. **Tokenize** — `vit5-large-vietnews` dùng SentencePiece âm tiết
   tiếng Việt. Cap input ở 1024 token.
2. **Prefix prompt** — chèn `vietnews:`, `legal:`, hoặc `dialogue:`
   trước input để chỉ định văn phong.
3. **Generate** — beam search 4 chùm, `length_penalty=2.0`, `no_repeat_ngram_size=3`.
4. **Decode** — bỏ token đặc biệt, NFC-normalize, trả về.

Truyền cả tài liệu, không cắt theo câu — mô hình tự cô đọng cấu trúc
diễn ngôn (đoạn mở, thân, kết).

## Giới hạn đã biết

- **Cap 1024 token đầu vào.** Bài dài hơn thì cắt thẳng — không có
  chunk-and-merge ở v0. Cho hợp đồng dài cần chia đoạn theo tay.
- **Tóm tắt rút trích, không tổng hợp.** Mô hình chọn cụm câu trong
  bài rồi nén lại — không phát sinh ý mới hoặc paraphrase mạnh. Nếu
  cần tóm tắt phong cách "human", đổi sang LLM trò chuyện qua
  `nom.chat` với prompt phù hợp.
- **Hallucination số liệu.** Bench nội bộ
  ([baseline JSON](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/accuracy/summarize_wiki_vi_baseline.json),
  n=10 trên `wiki_vi`): **1/10 mẫu thêm năm "2025" không có trong
  input** (bài về TP.HCM). Trên một mẫu khác (đoạn 234 ký tự về
  Việt Nam), mô hình tự bịa ra con số GDP "6,8 % – 7,0 %" không có
  trong nguồn. **Không dùng cho tổng hợp pháp lý / tài chính** mà
  không kiểm chứng số liệu — số mẫu nhỏ nên đây là cảnh báo định
  hướng, không phải đo định lượng đầy đủ.
- **Ngôn ngữ.** Chỉ tiếng Việt; văn bản tiếng Anh sẽ được mô hình cố
  dịch thô — không khuyến nghị.

## Mô hình thay thế

| Mô hình | License | Khi nào chọn |
| --- | --- | --- |
| `VietAI/vit5-large-vietnews` *(mặc định)* | Apache 2.0 | Tin tức / báo chí |
| `VietAI/vit5-base-vietnews` | Apache 2.0 | Máy 4 GB RAM, độ chính xác giảm ~3 ROUGE |
| LLM trò chuyện qua `nom.chat` | tuỳ | Cần kiểm soát phong cách / tóm tắt theo prompt cụ thể |

## Liên quan

- [Phân loại văn phong](./register.md) — tự động chọn prefix phù hợp.
- [Khôi phục dấu](./diacritic-restoration.md) — chạy trước nếu input
  thiếu dấu (hơi mặn cho summarizer).
