---
layout: home

title: Nôm
titleTemplate: Bộ công cụ AI tiếng Việt

hero:
  name: Nôm 喃
  text: Bộ công cụ AI tiếng Việt
  tagline: Khôi phục dấu, sửa chính tả, OCR, RAG cục bộ — mã nguồn mở, dành cho tiếng Việt.
  image:
    src: /logo.svg
    alt: Nôm — chữ 喃
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
  - icon:
      src: /icons/pen-line.svg
      width: 32
      height: 32
    title: Khôi phục dấu
    details: 'Mô hình <code>nrl-ai/vn-diacritic-vit5-base</code> đạt <strong>97.4 % word accuracy</strong> trung bình trên 4 register (hành chính / kinh doanh / hội thoại / văn học). Bản <code>vn-diacritic-small</code> 115M tham số, nhanh gấp 3 lần.'
    link: /tasks/diacritic-restoration
    linkText: Tài liệu khôi phục dấu

  - icon:
      src: /icons/spell-check.svg
      width: 32
      height: 32
    title: Sửa chính tả
    details: '<code>nrl-ai/vn-spell-correction-base</code> xử lý lỗi gõ Telex, lỗi OCR, viết tắt teen-code trong một lượt. <strong>98.58 % light · 97.35 % heavy</strong> trên 8-split eval grid — vượt baseline công khai 11–25 pp.'
    link: /tasks/spell-correction
    linkText: Tài liệu sửa chính tả

  - icon:
      src: /icons/layers.svg
      width: 32
      height: 32
    title: RAG cục bộ
    details: 'Pipeline: tài liệu → chunk → embed → retrieve → rerank → trả lời. Embedder <code>bkai-foundation-models</code>, Reranker <code>BAAI/bge-reranker-v2-m3</code>, LLM chạy cục bộ qua Ollama. Đo trên Zalo Legal QA, ViQuAD, MIRACL-vi.'
    link: /architecture
    linkText: Kiến trúc

  - icon:
      src: /icons/terminal.svg
      width: 32
      height: 32
    title: Cài một lệnh
    details: '<code>pip install nom-vn</code> cho phần lõi · <code>pip install &quot;nom-vn[chat]&quot;</code> kèm web chat app. Hoạt động ngoại tuyến, không gọi cloud API thuê bao, dữ liệu không rời máy.'
    link: /vi/quickstart
    linkText: Cài đặt
---

<div class="vp-doc home-extra">

<div class="ev-marquee" aria-hidden="true">
<div class="ev-marquee-track">
<span>khôi phục dấu</span><span>sửa chính tả</span><span>ocr tiếng việt</span><span>rag cục bộ</span><span>tách từ</span><span>chunking văn bản</span><span>embedder bkai</span><span>reranker bge-m3</span><span>tesseract vie</span><span>ollama</span><span>fastapi + react</span><span>apache 2.0</span><span>khôi phục dấu</span><span>sửa chính tả</span><span>ocr tiếng việt</span><span>rag cục bộ</span><span>tách từ</span><span>chunking văn bản</span><span>embedder bkai</span><span>reranker bge-m3</span><span>tesseract vie</span><span>ollama</span><span>fastapi + react</span><span>apache 2.0</span>
</div>
</div>

<div class="ev-section">
<h2>§ 02 · Bốn lựa chọn nên có ngay</h2>
<p class="lede">Mỗi gợi ý đều có script đo trong <code>benchmarks/</code> — chạy được từ một bản clone sạch, không có số phỏng đoán.</p>
</div>

<div class="ev-corners">
<div class="ev-corner featured">
<div class="ev-corner-head">
<span class="marker">01 · mặc định</span>
</div>
<h3>vn-diacritic-vit5-base</h3>
<p>Khôi phục dấu trên 4 register, trung bình <strong>97.4 %</strong>. Cân bằng giữa hành chính / kinh doanh / hội thoại / văn học. 220M tham số, giấy phép Apache 2.0.</p>
<a href="/tasks/diacritic-restoration" class="ev-corner-link">tài liệu</a>
</div>

<div class="ev-corner">
<div class="ev-corner-head">
<span class="marker">02 · sửa lỗi</span>
</div>
<h3>vn-spell-correction-base</h3>
<p>Một lượt cho cả lỗi gõ Telex, lỗi OCR, viết tắt teen-code và mất dấu. <strong>98.58 % light · 97.35 % heavy</strong> trên 8-split eval grid.</p>
<a href="/tasks/spell-correction" class="ev-corner-link">tài liệu</a>
</div>

<div class="ev-corner">
<div class="ev-corner-head">
<span class="marker">03 · rag cục bộ</span>
</div>
<h3>bkai bi-encoder + bge-reranker</h3>
<p>Embedder Apache 2.0 fine-tune trên Zalo Legal: <strong>R@1 76.25 %</strong>. Ghép cùng Reranker <code>BAAI/bge-reranker-v2-m3</code> cho điểm cuối <strong>R@1 86.3 %</strong>.</p>
<a href="/architecture" class="ev-corner-link">kiến trúc</a>
</div>

<div class="ev-corner">
<div class="ev-corner-head">
<span class="marker">04 · cài đặt</span>
</div>
<h3>pip install nom-vn[chat]</h3>
<p>Một lệnh là có sẵn FastAPI + React UI, parser PDF/DOCX/XLSX/PPTX, Embedder, Retrieval và Reranker. <code>nom serve</code> mở <code>localhost:8080</code>.</p>
<a href="/vi/quickstart" class="ev-corner-link">cài đặt</a>
</div>
</div>

<div class="ev-section">
<h2>§ 03 · Pipeline RAG</h2>
<p class="lede">Sáu bước, mỗi bước là một module thay thế được qua <code>Protocol</code> — không khoá vào nhà cung cấp nào.</p>
</div>

</div>

```mermaid
flowchart LR
    A[Tài liệu<br/>PDF · DOCX · ảnh] --> B[Cắt đoạn<br/>theo cú pháp Việt]
    B --> C[Embedder<br/>bkai bi-encoder]
    C --> D[Retrieval<br/>BM25 + dense]
    D --> E[Reranker<br/>bge-reranker-v2-m3]
    E --> F[LLM trả lời<br/>Ollama cục bộ]
    F --> G[Câu trả lời<br/>kèm trích dẫn]

    classDef step fill:#f1ede3,stroke:#141414,stroke-width:1px,color:#141414
    classDef out fill:#b5563a,stroke:#b5563a,color:#f1ede3
    class A,B,C,D,E,F step
    class G out
```

<div class="vp-doc home-extra">

<div class="ev-section">
<h2>§ 04 · Triết lý vận hành</h2>
<p class="lede">Bốn nguyên tắc bất di bất dịch — đã thấm vào mọi commit và mọi con số trên trang này.</p>
</div>

<div class="ev-principles">

<div class="ev-principle">
<div class="num">P · 01</div>
<div class="title">Đo trước, công bố sau</div>
<div class="body">Mọi con số xuất hiện trong tài liệu hay model card đều có script <code>benchmarks/…</code> chạy được từ một bản clone sạch và file kết quả JSON commit trong repo. Khi chưa đo, chúng tôi để trống thay vì viết "TBD" — minh bạch là điều kiện tiên quyết.</div>
</div>

<div class="ev-principle">
<div class="num">P · 02</div>
<div class="title">Riêng tư mặc định</div>
<div class="body">Không gọi cloud API thuê bao mặc định; mọi mô hình chạy cục bộ qua Ollama hoặc trên CPU/GPU của bạn. Dữ liệu nhạy cảm — hợp đồng, hồ sơ y tế, tài liệu nội bộ — không rời máy người dùng.</div>
</div>

<div class="ev-principle">
<div class="num">P · 03</div>
<div class="title">Bảo mật supply chain</div>
<div class="body">Loại bỏ phụ thuộc kèm file pickle (<code>.pkl</code>); ưu tiên <code>safetensors</code>. Mỗi mô hình bên thứ ba có SHA256 được audit, được pin theo revision, và được giải thích lý do trong docstring của wrapper.</div>
</div>

<div class="ev-principle">
<div class="num">P · 04</div>
<div class="title">Đa register</div>
<div class="body">Mọi mô hình được đo trên ít nhất hai register khác nhau (kinh doanh + văn học, hoặc in-domain + out-of-domain). Khoảng cách >10 pp giữa các register là dấu hiệu over-fit và sẽ được ghi rõ trong model card thay vì bị che giấu.</div>
</div>

</div>

## Cộng đồng

* **Hỏi đáp / báo lỗi:** [GitHub Issues](https://github.com/nrl-ai/nom-vn/issues)
* **Pull request:** xem [CONTRIBUTING](https://github.com/nrl-ai/nom-vn/blob/main/CONTRIBUTING.md)
* **Mô hình + dữ liệu:** [huggingface.co/nrl-ai](https://huggingface.co/nrl-ai)
* **Liên hệ tác giả chính:** [vietanh@nrl.ai](mailto:vietanh@nrl.ai) · Neural Research Lab

</div>
