# Tác vụ

Tài liệu tổ chức theo từng tác vụ end-user. Mỗi trang tổng hợp:
bức tranh công khai, mô hình `nrl-ai/*` đã huấn luyện (nếu có), số đo
trên cùng register grid, và lệnh tái lập.

## Tác vụ về văn bản

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **Khôi phục dấu** — thêm thanh và nguyên âm vào ASCII tiếng Việt | đã ship `nrl-ai/vn-diacritic-vit5-base` v0.2.29 | [→](/tasks/diacritic-restoration) |
| **Sửa chính tả** — siêu tập của khôi phục dấu, vá lỗi ký tự + Telex + OCR | đã ship `nrl-ai/vn-spell-correction-base` v0.2.29 (SOTA OOD) | [→](/tasks/spell-correction) |
| **Chuẩn hoá văn bản** — NFC/NFD, strip dấu, kiểm tra VN | shipped trong `nom.text` | [→](/tasks/text-normalization) |
| **Tách từ** — segment tiếng Việt không dấu phụ | rule-based + underthesea | [→](/tasks/word-segmentation) |
| **Phân loại văn phong** — trang trọng / kinh doanh / hội thoại / văn học | lexicon + PhoBERT-base | [→](/tasks/register) |
| **Tóm tắt** — cô đọng văn bản dài về tin tức / hợp đồng / hội thoại | shipped trong `nom.summarize` (ViT5-large) | [→](/tasks/summarize) |

## Tác vụ về tài liệu

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **OCR (chữ in)** — text từ ảnh / PDF scan | Tesseract `vie` (best printed); VLM cảnh báo | [→](/tasks/ocr) |
| **OCR chữ viết tay** — biểu mẫu, ghi chú, CMND/CCCD | shipped trong `nom.ocr.handwriting` (Vintern-1B) | [→](/tasks/handwriting) |
| **PDF text extraction** — text-layer cho PDF born-digital | pypdfium2 (BSD-3) | [→](/tasks/pdf-extraction) |
| **Chuyển định dạng** — PDF / ảnh → DOCX có thể chỉnh sửa | shipped trong `nom.convert` | [→](/tasks/convert) |
| **Dịch thuật** — Việt · Anh · 中 · 한 · 日, giữ định dạng `.docx`/`.xlsx`/`.pptx`/`.txt` | shipped trong `nom.translate` v0.1 | [→](/tasks/translate) |
| **Giọng nói → văn bản** — phỏng vấn, cuộc họp, ghi chú audio | shipped trong `nom.stt` (PhoWhisper-large) | [→](/tasks/stt) |

## Tác vụ về retrieval / RAG

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **Embedding (dense retrieval)** — vector hoá câu/đoạn VN | bkai-vietnamese-bi-encoder (76.25 % R@1) | [→](/tasks/embedding) |
| **Reranker** — xếp lại kết quả retrieval | bge-reranker-v2-m3 | [→](/tasks/reranker) |
| **RAG end-to-end** — chunk → embed → retrieve → rerank → trả lời | shipped trong `nom serve` | [→](/tasks/rag) |

## Tác vụ phân tích văn bản

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **Trích xuất thực thể** — PER/ORG/LOC/DATE/MONEY + LAW_REF/ID_VN/PHONE_VN cho VN pháp lý | shipped trong `nom.nlp.ner` | [→](/tasks/ner) |
| **NER + cảm xúc + nhận diện ngôn ngữ** — thư viện đầy đủ | shipped trong `nom.nlp` | [→](/tasks/nlp) |

## Vận hành

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **Hàng đợi xử lý** — theo dõi tác vụ chạy nền + tiến độ + huỷ | shipped trong `nom.chat.bgjobs` | [→](/tasks/jobs) |
| **Quản lý mô hình** — cài / theo dõi / xoá mô hình AI cục bộ | shipped trong `nom.chat.models_api` | [→](/tasks/models) |

## Multi-agent & MCP

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **Agent runtime** — 6 pattern Anthropic + 4 recipe sẵn dùng | shipped trong `nom.agents` | [→](/tasks/agents) |
| **MCP bridge** — server expose tools, client consume external | shipped trong `nom.mcp` | [→](/tasks/mcp) |

## Quy ước

- Mỗi trang theo [`_template.md`](_template.md) — TL;DR / public landscape
  / our pipeline / trained models / datasets / measured results / reproduce.
- Số nào cũng tái lập được từ một bản clone sạch.
- Số trống thay vì đoán — minh bạch là điều kiện tiên quyết.
