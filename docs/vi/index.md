# Giới thiệu

**Nôm** là bộ công cụ AI mã nguồn mở dành cho tiếng Việt. Trang tài liệu
này tập hợp toàn bộ thiết kế, kết quả đo, công thức triển khai và hướng
dẫn cộng đồng cho dự án.

> Tên gọi *Nôm* lấy cảm hứng từ chữ Nôm lịch sử, nhưng phạm vi của dự
> án là **tiếng Việt hiện đại viết bằng chữ Quốc Ngữ**. Chúng tôi không
> xử lý văn bản Hán-Nôm.

## Bốn mảng chức năng

1. **Khôi phục dấu** (`nom.text.fix_diacritics`) — `Toi yu Vit Nam`
   → `Tôi yêu Việt Nam`. Mô hình `nrl-ai/vn-diacritic-vit5-base` đạt
   97.4 % word accuracy trung bình trên 4 register.
2. **Sửa chính tả** (`nrl-ai/vn-spell-correction-*`) — siêu tập của
   khôi phục dấu, cộng thêm sửa lỗi ký tự, gõ Telex, OCR, viết tắt
   teen-code. 98.58 % light · 97.35 % heavy trên 8-split eval grid
   (xem [bench](/benchmark) và [trang task](/tasks/spell-correction)).
3. **OCR + bóc tách tài liệu** — pipeline cho PDF / DOCX / hình ảnh
   tiếng Việt với Tesseract `vie` và VLM dự phòng.
4. **RAG cục bộ** — Embedder (`bkai-foundation-models`), Retrieval,
   BM25 hybrid, Reranker (`BAAI/bge-reranker-v2-m3`), LLM cục bộ qua
   Ollama. Toàn bộ chạy ngoại tuyến.

## Triết lý

* **Đo trước, công bố sau.** Mọi con số trong tài liệu đều có script
  `benchmarks/...` chạy được từ một bản clone sạch.
* **Bảo mật supply chain.** Loại bỏ các phụ thuộc kèm pickle
  (`.pkl`); ưu tiên `safetensors`. Dùng SHA256 fingerprint cho mọi
  mô hình bên thứ ba.
* **Riêng tư.** Không gọi cloud API thuê bao mặc định; dữ liệu nhạy
  cảm không rời máy người dùng.
* **Đa register.** Mọi mô hình được đo trên ít nhất 2 register khác
  nhau (kinh doanh + văn học, hoặc in-domain + out-of-domain).

## Bắt đầu nhanh

* [Cài đặt và chạy thử](/vi/quickstart)
* [Danh sách mô hình đã huấn luyện](/vi/models)
* [Bench tổng hợp](/benchmark)

## Đóng góp

* Báo lỗi, đề xuất tính năng: [GitHub Issues](https://github.com/nrl-ai/nom-vn/issues)
* Quy ước đóng góp: [CONTRIBUTING](https://github.com/nrl-ai/nom-vn/blob/main/CONTRIBUTING.md)
* Liên hệ tác giả chính: [vietanh@nrl.ai](mailto:vietanh@nrl.ai) · Neural Research Lab
