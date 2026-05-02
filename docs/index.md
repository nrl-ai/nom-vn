---
layout: home

title: Nôm
titleTemplate: Bộ công cụ AI tiếng Việt

hero:
  name: Nôm 喃
  text: AI tiếng Việt — chạy trên máy của bạn
  tagline: Hỏi đáp tài liệu, đọc PDF / Word / Excel / PowerPoint, khôi phục dấu, sửa chính tả, OCR. Mọi thứ chạy nội bộ qua Ollama hoặc CPU. Dữ liệu của bạn không rời máy.
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
      src: /icons/layers.svg
      width: 32
      height: 32
    title: Hỏi đáp trên kho tài liệu của bạn
    details: 'Tải hợp đồng, báo cáo, PDF scan, biểu mẫu, công văn lên — Nôm cắt đoạn, sinh vector, tra cứu, xếp hạng lại, rồi trả lời kèm trích dẫn. Embedder <code>bkai-foundation-models</code>, Reranker <code>BAAI/bge-reranker-v2-m3</code>. Đo trên Zalo Legal QA: <strong>R@1 86.3 %</strong>.'
    link: /tasks/rag
    linkText: Tài liệu RAG
  - icon:
      src: /icons/pen-line.svg
      width: 32
      height: 32
    title: Sửa văn bản — dấu, chính tả, gõ Telex
    details: 'Mô hình <code>nrl-ai/vn-spell-correction-base</code> v0.2.29 xử lý gọn lỗi gõ, lỗi OCR và mất dấu trong một lượt. <strong>98.32 % light · 97.03 % heavy</strong> trên 8 tập kiểm thử; <strong>79.62 %</strong> trên tập 150 câu hand-curate ngoài phân phối — vượt Toshiiiii1.'
    link: /tasks/spell-correction
    linkText: Tài liệu sửa chính tả
  - icon:
      src: /icons/spell-check.svg
      width: 32
      height: 32
    title: Đọc tài liệu giấy / PDF scan
    details: 'OCR tiếng Việt qua Tesseract <code>vie</code> cho ảnh / PDF scan, kết hợp tự động sửa chính tả sau OCR để đỡ lỗi máy quét. PDF born-digital dùng pypdfium2 — không OCR thừa, không mất bố cục.'
    link: /tasks/ocr
    linkText: Tài liệu OCR
  - icon:
      src: /icons/terminal.svg
      width: 32
      height: 32
    title: Một lệnh là chạy
    details: '<code>pip install nom-vn[chat]</code> kèm sẵn FastAPI + React UI, parser PDF / DOCX / XLSX / PPTX, embedder, retrieval và reranker. <code>nom serve</code> mở <code>localhost:8080</code>. Hoạt động ngoại tuyến, không gọi đám mây thuê bao.'
    link: /vi/quickstart
    linkText: Cài đặt
---

<div class="vp-doc home-extra">

<div class="ev-marquee" aria-hidden="true">
<div class="ev-marquee-track">
<span>hỏi đáp tài liệu</span><span>khôi phục dấu</span><span>sửa chính tả</span><span>ocr tiếng việt</span><span>đọc pdf · word · excel · ppt</span><span>tách từ</span><span>chunking</span><span>embedder bkai</span><span>reranker bge-m3</span><span>tesseract vie</span><span>ollama</span><span>fastapi + react</span><span>apache 2.0</span><span>hỏi đáp tài liệu</span><span>khôi phục dấu</span><span>sửa chính tả</span><span>ocr tiếng việt</span><span>đọc pdf · word · excel · ppt</span><span>tách từ</span><span>chunking</span><span>embedder bkai</span><span>reranker bge-m3</span><span>tesseract vie</span><span>ollama</span><span>fastapi + react</span><span>apache 2.0</span>
</div>
</div>

<div class="ev-section">
<h2>§ 02 · Sản phẩm thấy được</h2>
<p class="lede">Một lệnh <code>nom serve</code> là có giao diện web đầy đủ chạy ngay trên máy của bạn — không phải chỉ một thư viện trong terminal.</p>
</div>

<div class="ev-shots">

<figure class="ev-shot ev-shot-wide">
<a href="/screenshots/02-chat-with-answer.png" target="_blank" rel="noopener">
<img src="/screenshots/02-chat-with-answer.png" alt="Giao diện hỏi đáp với câu trả lời và trích dẫn" loading="lazy" />
</a>
<figcaption><strong>Hỏi đáp trên không gian "Hợp đồng &amp; Báo cáo".</strong> Câu trả lời kèm trích dẫn được liên kết về tài liệu nguồn — bạn click vào để xem đoạn gốc.</figcaption>
</figure>

<figure class="ev-shot">
<a href="/screenshots/04-viewer-docx.png" target="_blank" rel="noopener">
<img src="/screenshots/04-viewer-docx.png" alt="Bóc tách nội dung từ DOCX" loading="lazy" />
</a>
<figcaption><strong>Bóc tách DOCX / XLSX / PPTX.</strong> Giữ nguyên đầu trang, bảng và cấu trúc. Xem được cả văn bản gốc và phần đã trích.</figcaption>
</figure>

<figure class="ev-shot">
<a href="/screenshots/07-playground-diacritic.png" target="_blank" rel="noopener">
<img src="/screenshots/07-playground-diacritic.png" alt="Khôi phục dấu cho hợp đồng tiếng Việt không dấu" loading="lazy" />
</a>
<figcaption><strong>Khôi phục dấu trực tiếp.</strong> Dán văn bản không dấu, chọn register (kinh doanh, hội thoại, văn học...), chọn backend (rule / mô hình HF / LLM) — chạy thẳng trên máy.</figcaption>
</figure>

<figure class="ev-shot">
<a href="/screenshots/12-playground-api.png" target="_blank" rel="noopener">
<img src="/screenshots/12-playground-api.png" alt="Tài liệu API và ví dụ cURL" loading="lazy" />
</a>
<figcaption><strong>API và ví dụ tích hợp.</strong> Mọi tác vụ có sẵn endpoint REST. Dán cURL hoặc dùng thư viện Python để ghép vào hệ thống của bạn.</figcaption>
</figure>

</div>

<p class="ev-shots-foot"><a href="/vi/quickstart">Cài và mở thử trong 2 phút →</a></p>

<div class="ev-section">
<h2>§ 03 · Bốn việc bạn có thể làm ngay</h2>
<p class="lede">Mỗi khả năng đều có script đo trong <code>benchmarks/</code> — chạy được từ một bản clone sạch, không có số phỏng đoán.</p>
</div>

<div class="ev-corners">

<div class="ev-corner featured">
<div class="ev-corner-head"><span class="marker">01 · phổ biến nhất</span></div>
<h3>Hỏi đáp trên kho tài liệu nội bộ</h3>
<p>Hợp đồng, báo cáo, PDF scan, biểu mẫu, công văn — toàn bộ ở lại trong máy của bạn. Pipeline tra cứu đo trên Zalo Legal QA: bkai bi-encoder + bge-reranker → <strong>R@1 86.3 %</strong>. Có UI hỏi đáp và trích dẫn sẵn.</p>
<a href="/tasks/rag" class="ev-corner-link">tài liệu RAG</a>
</div>

<div class="ev-corner">
<div class="ev-corner-head"><span class="marker">02 · sửa văn bản</span></div>
<h3>Khôi phục dấu, sửa chính tả</h3>
<p>Một lượt cho cả lỗi gõ Telex, lỗi OCR, viết tắt teen-code và mất dấu. <code>nrl-ai/vn-spell-correction-base</code> v0.2.29: <strong>98.32 % light · 97.03 % heavy</strong> trên 8 tập kiểm thử; <strong>79.62 %</strong> trên tập ngoài phân phối.</p>
<a href="/tasks/spell-correction" class="ev-corner-link">tài liệu sửa chính tả</a>
</div>

<div class="ev-corner">
<div class="ev-corner-head"><span class="marker">03 · giấy thành chữ</span></div>
<h3>OCR tiếng Việt cho tài liệu scan</h3>
<p>Tesseract <code>vie</code> cho ảnh / PDF scan, kết hợp sửa chính tả sau OCR để đỡ lỗi máy quét. PDF born-digital đi qua pypdfium2 — không OCR thừa, không mất bố cục bảng.</p>
<a href="/tasks/ocr" class="ev-corner-link">tài liệu OCR</a>
</div>

<div class="ev-corner">
<div class="ev-corner-head"><span class="marker">04 · tích hợp</span></div>
<h3>Lập trình ghép vào hệ thống có sẵn</h3>
<p>Thư viện Python type-annotated, Protocol-based — không khoá vào lớp cụ thể. REST API theo OpenAPI 3.1. <code>pip install nom-vn[chat]</code> đầy đủ web app + parser + retrieval + rerank.</p>
<a href="/vi/quickstart" class="ev-corner-link">cài đặt</a>
</div>

</div>

<div class="ev-section">
<h2>§ 04 · Pipeline RAG</h2>
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
<h2>§ 05 · Triết lý vận hành</h2>
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
<div class="body">Không gọi đám mây thuê bao mặc định; mọi mô hình chạy nội bộ qua Ollama hoặc trên CPU/GPU của bạn. Dữ liệu nhạy cảm — hợp đồng, hồ sơ y tế, tài liệu nội bộ — không rời máy người dùng.</div>
</div>

<div class="ev-principle">
<div class="num">P · 03</div>
<div class="title">Bảo mật nguồn gốc phần mềm</div>
<div class="body">Loại bỏ phụ thuộc kèm tệp pickle (<code>.pkl</code>); ưu tiên <code>safetensors</code>. Mỗi mô hình bên thứ ba có bản băm SHA256 được audit, được pin theo phiên bản, và được giải thích lý do trong tài liệu của lớp bao bọc.</div>
</div>

<div class="ev-principle">
<div class="num">P · 04</div>
<div class="title">Đa register</div>
<div class="body">Mọi mô hình được đo trên ít nhất hai register khác nhau (kinh doanh + văn học, hoặc trong-miền + ngoài-miền). Khoảng cách >10 pp giữa các register là dấu hiệu over-fit và sẽ được ghi rõ trong model card thay vì bị che giấu.</div>
</div>

</div>

<div class="ev-section">
<h2>§ 06 · Đi đâu tiếp</h2>
<p class="lede">Tuỳ bạn đang ở vai gì — học hỏi, tự cài, hay đánh giá cho doanh nghiệp.</p>
</div>

<div class="ev-next-grid">

<a class="ev-next" href="/vi/quickstart">
<div class="marker">cho lập trình viên</div>
<h3>Cài và chạy trong 2 phút</h3>
<p>Một lệnh <code>pip install nom-vn[chat]</code>, một lệnh <code>nom serve</code>. Mở <code>localhost:8080</code> và bắt đầu hỏi.</p>
<span class="ev-next-cta">Cài đặt nhanh →</span>
</a>

<a class="ev-next" href="/tasks/">
<div class="marker">cho nhà nghiên cứu</div>
<h3>Số đo trên 4 register</h3>
<p>Mỗi tác vụ — khôi phục dấu, sửa chính tả, OCR, tách từ, embedding, reranker, RAG — có trang riêng kèm số đo và lệnh tái lập.</p>
<span class="ev-next-cta">Xem các tác vụ →</span>
</a>

<a class="ev-next" href="/doanh-nghiep/">
<div class="marker">cho doanh nghiệp</div>
<h3>Triển khai nội bộ + hợp đồng cam kết</h3>
<p>Tự cài / vùng riêng đám mây / mạng cô lập. Tuân thủ Nghị định 13/2023, có hợp đồng SLA, đào tạo trực tiếp.</p>
<span class="ev-next-cta">Phiên bản doanh nghiệp →</span>
</a>

</div>

## Cộng đồng

* **Hỏi đáp / báo lỗi:** [GitHub Issues](https://github.com/nrl-ai/nom-vn/issues)
* **Pull request:** xem [CONTRIBUTING](https://github.com/nrl-ai/nom-vn/blob/main/CONTRIBUTING.md)
* **Mô hình + dữ liệu:** [huggingface.co/nrl-ai](https://huggingface.co/nrl-ai)
* **Liên hệ tác giả chính:** [vietanh@nrl.ai](mailto:vietanh@nrl.ai) · Neural Research Lab

</div>
