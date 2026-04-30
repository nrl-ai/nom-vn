---
layout: home

title: Nôm
titleTemplate: Bộ công cụ AI tiếng Việt

hero:
  name: Nôm
  text: Bộ công cụ AI tiếng Việt
  tagline: Khôi phục dấu, sửa chính tả, OCR, RAG cục bộ — mã nguồn mở, ưu tiên tiếng Việt.
  image:
    src: /logo.svg
    alt: Nôm
  actions:
    - theme: brand
      text: Bắt đầu
      link: /vi/quickstart
    - theme: alt
      text: Xem trên GitHub
      link: https://github.com/nrl-ai/nom-vn
    - theme: alt
      text: Hugging Face
      link: https://huggingface.co/nrl-ai

features:
  - icon: ✍️
    title: Khôi phục dấu
    details: |
      Mô hình `nrl-ai/vn-diacritic-base` đạt **97.4 % độ chính xác từ** trung bình
      trên 4 register (kinh doanh / hành chính / hội thoại / văn học). Bản nhỏ
      `vn-diacritic-fast` 115 M tham số, 3× nhanh hơn.
    link: /tasks/diacritic-restoration
    linkText: Tài liệu khôi phục dấu

  - icon: 🛠️
    title: Sửa chính tả
    details: |
      `nrl-ai/vn-spell-correction-base` xử lý cả lỗi gõ Telex, OCR, và lỗi viết tắt
      teen-code trong một bước. Trung bình **98.58 % light · 97.35 % heavy** trên
      8-split eval grid — vượt baseline công khai 11-25 pp.
    link: /tasks/spell-correction
    linkText: Tài liệu sửa chính tả

  - icon: 🧠
    title: RAG cục bộ
    details: |
      Pipeline tài liệu → chunk → embed → retrieve → rerank → trả lời. Embedder
      tiếng Việt `bkai-foundation-models`, reranker `BAAI/bge-reranker-v2-m3`,
      LLM cục bộ qua Ollama. Đo trên Zalo Legal QA, ViQuAD, MIRACL-vi.
    link: /architecture
    linkText: Kiến trúc

  - icon: 📦
    title: Cài 1 lệnh
    details: |
      `pip install nom-vn` cho phần lõi · `pip install "nom-vn[chat]"` thêm
      ứng dụng web chat. Hoạt động ngoại tuyến, không gọi API thuê bao,
      dữ liệu không rời máy.
    link: /vi/quickstart
    linkText: Cài đặt
---

<div class="vp-doc home-extra">

## Đo lường thực tế, không phải hứa hẹn

Tất cả số liệu trên trang này đều có script `benchmarks/...` chạy được
từ một bản clone sạch và file kết quả JSON cam kết trong repo. Khi không
có số đo, chúng tôi để trống thay vì viết "TBD" — minh bạch là điều
kiện tiên quyết.

## Cộng đồng

* **Hỏi đáp / báo lỗi:** [GitHub Issues](https://github.com/nrl-ai/nom-vn/issues)
* **Pull request:** xem [CONTRIBUTING](https://github.com/nrl-ai/nom-vn/blob/main/CONTRIBUTING.md)
* **Mô hình + dữ liệu:** [huggingface.co/nrl-ai](https://huggingface.co/nrl-ai)

</div>
