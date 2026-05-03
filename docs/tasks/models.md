# Quản lý mô hình

Cài đặt, theo dõi và xoá các mô hình AI chạy cục bộ — LLM trò chuyện
qua Ollama, mô hình chuyên dụng từ HuggingFace, công cụ hệ thống như
Tesseract.

## Vì sao có trang này

Nôm chạy hoàn toàn cục bộ. Mỗi tác vụ (chat, dịch, OCR, sửa chính tả)
cần ít nhất một mô hình tương ứng phải có trên máy. Trang **Mô hình**
là điểm trung tâm để biết:

- Mô hình nào đã cài, dung lượng bao nhiêu.
- Mô hình nào nên cài thêm cho tác vụ cụ thể.
- Mô hình đang tải, tiến độ bao nhiêu.

## Cách dùng

### Trong giao diện web

Vào **Mô hình** ở thanh điều hướng bên trái (mục "Hệ thống"). Trang
chia thành các nhóm theo tác vụ:

- **Chat & RAG** — LLM trò chuyện (Qwen3, Gemma3 các kích cỡ).
- **Dịch thuật** — mô hình chuyên dụng MT (MADLAD, M2M100) + LLM phụ
  trợ.
- **Khôi phục dấu / sửa chính tả** — seq2seq chuyên dụng + LLM phụ trợ.
- **Truy xuất tài liệu (RAG)** — bộ embedder + reranker.
- **OCR / chuyển định dạng** — Tesseract.

Mỗi hàng có:

- Tên mô hình + nhãn cấp độ (Nhẹ / Tiêu chuẩn / Mạnh) + nguồn (Ollama
  / HuggingFace / Hệ thống).
- Mô tả ngắn — khi nào nên chọn mô hình này.
- Dung lượng tải về + RAM yêu cầu + license.
- **Tải** (cho mô hình Ollama có thể kéo qua API), **tự tải khi dùng**
  (cho mô hình HF — sẽ tự động tải khi chạy lần đầu), hoặc **cài hệ
  thống** (cho công cụ binary như Tesseract — phải dùng `apt` / `brew`).

Có thể chọn nhiều mô hình rồi bấm "Tải tất cả" để tải song song.

### Theo dõi tiến độ tải

Khi đang tải, panel "Đang tải" hiện lên với từng tác vụ kèm thanh tiến
độ. Polling xảy ra mỗi 1.5 giây trong khi còn tác vụ đang chạy; khi
mọi tác vụ xong, polling dừng để không tốn CPU vô ích.

### Gọi trực tiếp qua API HTTP

```bash
# Liệt kê toàn bộ
curl -s http://localhost:8080/api/models | jq

# Bắt đầu kéo một mô hình Ollama
curl -X POST http://localhost:8080/api/models/pull \
  -H "Content-Type: application/json" \
  -d '{"source":"ollama","model":"qwen3:8b"}'

# Bắt đầu kéo nhiều mô hình một lượt
curl -X POST http://localhost:8080/api/models/pull/batch \
  -H "Content-Type: application/json" \
  -d '{"models":["qwen3:8b","gemma3:4b"]}'

# Theo dõi
curl -s http://localhost:8080/api/models/pulls | jq

# Huỷ
curl -X POST http://localhost:8080/api/models/pull/{pull_id}/cancel

# Xoá mô hình Ollama đã cài
curl -X DELETE http://localhost:8080/api/models/ollama/qwen3:1.7b
```

## Cách chọn mô hình

### LLM trò chuyện (cho Chat / RAG / dịch / sửa dấu)

| Mô hình | Tier | RAM | Khi nào chọn |
| --- | --- | --- | --- |
| `qwen3:0.6b` | Nhẹ | 2 GB | Máy 4 GB RAM, ưu tiên tốc độ hơn chất lượng |
| `qwen3:1.7b` | Nhẹ | 4 GB | Cân bằng tốc độ / chất lượng cho desktop CPU |
| `qwen3:8b` *(mặc định)* | Tiêu chuẩn | 8 GB | Cài đặt mới — chất lượng đáng tin cậy |
| `qwen3:14b` | Mạnh | 16 GB | Chất lượng RAG cao nhất; cần GPU hoặc 32 GB RAM |
| `gemma3:4b` / `gemma3:12b` | Nhẹ / Mạnh | 6 / 16 GB | Lựa chọn thay thế Qwen3 với licence Gemma |

### Mô hình chuyên dụng (Dịch thuật)

| Mô hình | Khi nào chọn | Đo |
| --- | --- | --- |
| `google/madlad400-3b-mt` | EN ↔ VN có GPU | chrF 40.92 EN→VN, 260 ms/câu |
| `facebook/m2m100_418M` | Chỉ có CPU, hoặc 200 + ngôn ngữ khác | chrF 35.73 EN→VN, 870 ms/câu |

### Mô hình chuyên dụng (Sửa chính tả / Khôi phục dấu)

| Mô hình | Khi nào chọn |
| --- | --- |
| `nrl-ai/vn-spell-correction-base` | Sửa lỗi gõ + mất dấu + OCR + teencode trong một lượt |
| `nrl-ai/vn-diacritic-vit5-base` | Chỉ khôi phục dấu, nhỏ gọn hơn |
| `vinai/bartpho-syllable-base` | Backbone âm tiết cho biến thể nano |

### Bộ truy xuất (RAG)

| Mô hình | Vai trò |
| --- | --- |
| `bkai-foundation-models/vietnamese-bi-encoder` | Embedder mặc định |
| `BAAI/bge-reranker-v2-m3` | Cross-encoder xếp hạng lại sau bi-encoder |

R@1 86.3 % trên Zalo Legal QA khi kết hợp cả hai.

### OCR (Hệ thống)

| Công cụ | Cài bằng |
| --- | --- |
| `tesseract-ocr-vie` | `apt install tesseract-ocr-vie` (Linux) hoặc `brew install tesseract-lang` (macOS) |

## Cách hoạt động

### Phân nguồn

- **Ollama** — daemon HTTP cục bộ ở `localhost:11434`. Nôm gọi
  `/api/pull` qua HTTP, đọc luồng JSON từng dòng, tổng hợp tiến độ
  theo từng layer.
- **HuggingFace** — không kéo chủ động. Khi gọi mô hình lần đầu,
  `transformers` / `huggingface_hub` tự tải vào cache `~/.cache/huggingface/`.
  Nôm chỉ quét cache để hiển thị "đã có sẵn" trong giao diện.
- **Hệ thống** — Tesseract không có API kéo. Nôm kiểm tra binary có
  `tesseract` trong `PATH` không, hiển thị trạng thái phù hợp.

### Tải song song

API hỗ trợ tải tối đa 3 tác vụ cùng lúc (`_MAX_CONCURRENT_PULLS`).
Vượt quá thì trả 429 — UI hiển thị lỗi nhẹ, không chặn các tác vụ
khác đang chạy.

Tác vụ hoàn tất hoặc lỗi sẽ được giữ trong danh sách 5 phút (`_PULL_RETENTION_SECONDS`)
rồi tự dọn để giao diện không phình.

## Giới hạn đã biết

- **Chỉ kéo được mô hình Ollama qua API.** Mô hình HF tự tải khi
  dùng — không có cách "tải trước" qua giao diện. Cách thay thế:
  chạy script Python kích hoạt `transformers.AutoModel.from_pretrained(...)`
  một lần.
- **Không có cách xoá HF cache từ giao diện.** Dùng
  `huggingface-cli delete-cache` hoặc xoá trực tiếp
  `~/.cache/huggingface/hub/<repo>`.
- **Trạng thái Ollama "không sẵn sàng" không chặn UI.** Trang vẫn
  hiển thị catalog đề xuất; chỉ phần "Đã cài đặt" trống. Cài Ollama
  từ <https://ollama.com>.

## Liên quan

- [Hàng đợi xử lý](./jobs.md) — kéo qua API hiển thị trên trang Hàng đợi
  và mô hình mặc định.
