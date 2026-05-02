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

## Tác vụ về tài liệu

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **OCR** — text từ ảnh / PDF scan | Tesseract `vie` (best printed); VLM cảnh báo | [→](/tasks/ocr) |
| **PDF text extraction** — text-layer cho PDF born-digital | pypdfium2 (BSD-3) | [→](/tasks/pdf-extraction) |
| **Chuyển định dạng** — PDF / ảnh → DOCX có thể chỉnh sửa | shipped trong `nom.convert` | [→](/tasks/convert) |
| **Dịch thuật** — Việt ↔ Anh, giữ định dạng `.docx`/`.xlsx`/`.pptx`/`.txt` | shipped trong `nom.translate` v0.1 | [→](/tasks/translate) |

## Tác vụ về retrieval / RAG

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **Embedding (dense retrieval)** — vector hoá câu/đoạn VN | bkai-vietnamese-bi-encoder (76.25 % R@1) | [→](/tasks/embedding) |
| **Reranker** — xếp lại kết quả retrieval | bge-reranker-v2-m3 | [→](/tasks/reranker) |
| **RAG end-to-end** — chunk → embed → retrieve → rerank → trả lời | shipped trong `nom serve` | [→](/tasks/rag) |

## Tác vụ phân tích văn bản

| Tác vụ | Trạng thái | Trang |
|---|---|---|
| **NER + Sentiment + Lang detect** — entities, cảm xúc, ngôn ngữ | shipped trong `nom.nlp` | [→](/tasks/nlp) |

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
