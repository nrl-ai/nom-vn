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

<div class="ev-section">
<h2>§ 02 · Dùng được vào việc gì</h2>
<p class="lede">Mười hai tác vụ đã ship — mỗi tác vụ có trang riêng kèm số đo trên dữ liệu thật và lệnh tái lập từ một bản clone sạch.</p>
</div>

<div class="ev-usecases">

<a class="ev-usecase" href="/tasks/rag">
<div class="marker">01 · RAG</div>
<h3>Hỏi đáp trên kho tài liệu</h3>
<p>Tải PDF / DOCX / XLSX / PPTX / ảnh — Nôm cắt đoạn, sinh vector, tra cứu, xếp hạng lại, trả lời kèm trích dẫn. <strong>R@1 86,3 %</strong> trên Zalo Legal.</p>
<span class="ev-usecase-cta">Xem tài liệu RAG →</span>
</a>

<a class="ev-usecase" href="/tasks/translate">
<div class="marker">02 · dịch thuật</div>
<h3>Dịch Việt ↔ Anh giữ nguyên định dạng</h3>
<p>Dịch <code>.docx</code> / <code>.xlsx</code> / <code>.pptx</code> / <code>.txt</code> — giữ nguyên tiêu đề, bảng, cấu trúc. Chạy nội bộ qua Ollama hoặc gọi Claude / GPT cho tác vụ không nhạy cảm.</p>
<span class="ev-usecase-cta">Xem dịch thuật →</span>
</a>

<a class="ev-usecase" href="/tasks/convert">
<div class="marker">03 · chuyển định dạng</div>
<h3>PDF / ảnh → DOCX chỉnh sửa được</h3>
<p>OCR (Tesseract <code>vie</code> cho dòng in, Vintern cho viết tay), bóc bố cục, dựng lại DOCX với đoạn văn, bảng, đầu trang chân trang. Đầu vào để dịch, biên tập, hoặc lưu trữ.</p>
<span class="ev-usecase-cta">Xem chuyển định dạng →</span>
</a>

<a class="ev-usecase" href="/tasks/spell-correction">
<div class="marker">04 · sửa văn bản</div>
<h3>Khôi phục dấu + sửa chính tả</h3>
<p>Một mô hình ViT5 220 M xử lý gọn lỗi gõ Telex, mất dấu, lỗi OCR trong một lượt. <strong>98,32 %</strong> tổng hợp light · <strong>79,62 %</strong> OOD ngoài phân phối — vượt Toshiiiii1.</p>
<span class="ev-usecase-cta">Xem sửa chính tả →</span>
</a>

<a class="ev-usecase" href="/tasks/ocr">
<div class="marker">05 · OCR (chữ in)</div>
<h3>Đọc ảnh / PDF scan tiếng Việt</h3>
<p>Tesseract <code>vie</code> cho dòng in (<strong>CER 0,00 %</strong> sạch · 0,70 % nhiễu nhẹ), VietOCR cho chữ viết tay (<strong>CER 31,82 %</strong>) — vượt Tesseract 37,5 pp ở dòng viết tay.</p>
<span class="ev-usecase-cta">Xem OCR →</span>
</a>

<a class="ev-usecase" href="/tasks/handwriting">
<div class="marker">06 · OCR chữ viết tay</div>
<h3>Đọc biểu mẫu / ghi chú / CMND viết tay</h3>
<p>Vintern-1B-v3_5 (MIT, safetensors) qua VLM cấp trang. <strong>CER 0,47 % sạch / 0,37 % nhiễu</strong> trên 20 ảnh chữ in tổng hợp; cảnh báo: VLM ảo trên line crop hẹp, phải truyền cả trang.</p>
<span class="ev-usecase-cta">Xem OCR chữ viết tay →</span>
</a>

<a class="ev-usecase" href="/tasks/stt">
<div class="marker">07 · giọng nói → văn bản</div>
<h3>Chuyển ghi âm tiếng Việt thành văn bản</h3>
<p>PhoWhisper-large (BSD-3, VinAI fine-tune Whisper trên 844 giờ VN) hoặc Whisper-large-v3 (đa ngôn ngữ, audio lai EN/VN). Đo nội bộ n=3: <strong>WER 15,2 %</strong>; cần đo trên ViMD 3 vùng.</p>
<span class="ev-usecase-cta">Xem STT →</span>
</a>

<a class="ev-usecase" href="/tasks/summarize">
<div class="marker">08 · tóm tắt</div>
<h3>Tóm tắt báo / hợp đồng / hội thoại</h3>
<p>VietAI ViT5-large-vietnews (MIT, 866 M) với prefix theo văn phong. Upstream ROUGE-1 63,4 vietnews. <strong>Cảnh báo:</strong> mô hình có thể bịa số liệu cụ thể — đừng dùng cho pháp lý / tài chính nếu không kiểm chứng số.</p>
<span class="ev-usecase-cta">Xem tóm tắt →</span>
</a>

<a class="ev-usecase" href="/tasks/register">
<div class="marker">09 · phân loại văn phong</div>
<h3>Định tuyến văn bản theo thể loại</h3>
<p>Quy tắc heuristic 4 lớp (trang trọng / kinh doanh / hội thoại / văn học) — chạy ~1 ms cục bộ, không cần model. Đường PhoBERT fine-tune (mục tiêu macro-F1 ≥ 0,85) đã có script, đang chờ chạy.</p>
<span class="ev-usecase-cta">Xem phân loại văn phong →</span>
</a>

<a class="ev-usecase" href="/tasks/agents">
<div class="marker">10 · tác tử</div>
<h3>Tác tử AI gọi công cụ và MCP</h3>
<p>6 mẫu Anthropic (Single / Chain / Route / Parallel / Voting / Orchestrator-Evaluator) + cầu nối MCP để mở hoặc dùng công cụ ngoài. Streaming bằng SSE, có audit log.</p>
<span class="ev-usecase-cta">Xem tác tử →</span>
</a>

<a class="ev-usecase" href="/tasks/ner">
<div class="marker">11 · trích xuất thực thể</div>
<h3>NER chuẩn + bộ pháp lý VN</h3>
<p>Trích PER / ORG / LOC / DATE / MONEY (chuẩn) và <strong>LAW_REF</strong> (luật, điều, khoản) / <strong>ID_VN</strong> (CMND/CCCD) / <strong>PHONE_VN</strong> (bộ pháp lý) cho hợp đồng VN. Quy tắc, không cần GPU.</p>
<span class="ev-usecase-cta">Xem trích xuất thực thể →</span>
</a>

<a class="ev-usecase" href="/tasks/compliance">
<div class="marker">12 · tuân thủ</div>
<h3>Phân loại rủi ro AI · Luật 134/2025</h3>
<p>Phân loại theo 3 mức (cao / trung / thấp) đối chiếu Điều 8–15. Mỗi quyết định kèm điều luật áp dụng và lý do — đầu vào dạng tự nhiên, không cần nhãn thủ công.</p>
<span class="ev-usecase-cta">Xem tuân thủ →</span>
</a>

</div>

<div class="ev-section">
<h2>§ 03 · Sản phẩm thấy được</h2>
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
<a href="/screenshots/22-translate.png" target="_blank" rel="noopener">
<img src="/screenshots/22-translate.png" alt="Dịch thuật giữ nguyên định dạng .docx, .xlsx, .pptx, .txt" loading="lazy" />
</a>
<figcaption><strong>Dịch thuật giữ nguyên định dạng.</strong> Việt ↔ Anh cho <code>.docx</code> / <code>.xlsx</code> / <code>.pptx</code> / <code>.txt</code> — giữ nguyên tiêu đề, bảng, cấu trúc. Chuyển đổi PDF / ảnh sang DOCX qua OCR rồi dịch tiếp.</figcaption>
</figure>

<figure class="ev-shot">
<a href="/screenshots/12-playground-api.png" target="_blank" rel="noopener">
<img src="/screenshots/12-playground-api.png" alt="Tài liệu API và ví dụ cURL" loading="lazy" />
</a>
<figcaption><strong>API và ví dụ tích hợp.</strong> Mọi tác vụ có sẵn endpoint REST. Dán cURL hoặc dùng thư viện Python để ghép vào hệ thống của bạn.</figcaption>
</figure>

</div>

<p class="ev-shots-foot"><a href="/tasks/translate">Xem dịch thuật</a> · <a href="/tasks/convert">Xem chuyển định dạng</a> · <a href="/vi/quickstart">Cài và mở thử trong 2 phút →</a></p>

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
