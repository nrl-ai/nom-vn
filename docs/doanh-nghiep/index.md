---
description: Triển khai Nôm trên hạ tầng nội bộ — bảo mật theo Nghị định 13/2023, tuỳ biến mô hình theo dữ liệu của bạn, hỗ trợ trực tiếp từ Neural Research Lab.
outline: false
---

<div class="ev-enterprise-hero">
<div class="ev-enterprise-hero-meta">Phiên bản doanh nghiệp · Triển khai nội bộ · Tiếng Việt</div>

# Nôm cho doanh nghiệp

<p class="ev-enterprise-lede">
Bộ công cụ xử lý tiếng Việt mã nguồn mở mà cộng đồng đang dùng — đóng gói riêng cho ngân hàng, bảo hiểm, pháp chế và y tế. Cài trên máy chủ của bạn, dữ liệu không rời khỏi nội bộ, có hợp đồng cam kết và đội ngũ hỗ trợ trực tiếp.
</p>

<div class="ev-enterprise-actions">
<a href="#lien-he" class="ev-btn ev-btn-brand">Đặt lịch trao đổi 30 phút</a>
<a href="/doanh-nghiep/so-sanh-oss-ee" class="ev-btn ev-btn-alt">So sánh OSS vs Doanh nghiệp</a>
<a href="#cach-trien-khai" class="ev-btn ev-btn-alt">Xem các cách triển khai</a>
</div>

<div class="ev-enterprise-stats">
<div><strong>100 %</strong><span>chạy nội bộ — không thuê bao đám mây</span></div>
<div><strong>Apache 2.0</strong><span>nhân lõi mã nguồn mở</span></div>
<div><strong>Nghị định 13</strong><span>thiết kế tuân thủ</span></div>
<div><strong>Có gốc rõ ràng</strong><span>không pickle, không cửa sau</span></div>
</div>

</div>

<div class="ev-section">
<h2>§ 01 · Bài toán chúng tôi giải</h2>
<p class="lede">Doanh nghiệp Việt cần xử lý văn bản, hợp đồng và tài liệu tiếng Việt trong môi trường mà dữ liệu nhạy cảm không được phép ra khỏi nội bộ.</p>
</div>

<div class="ev-corners">
<div class="ev-corner">
<div class="ev-corner-head"><span class="marker">01 · pháp chế</span></div>
<h3>Tra cứu hợp đồng và quy định</h3>
<p>Tìm kiếm theo nghĩa trên kho hợp đồng, văn bản pháp luật và công văn nội bộ — toàn bộ vẫn ở trong mạng của bạn. Đo trên bộ Zalo Legal: <strong>tỷ lệ tìm đúng câu trả lời 86.3 %</strong> sau khi xếp hạng lại.</p>
</div>

<div class="ev-corner">
<div class="ev-corner-head"><span class="marker">02 · ngân hàng &amp; bảo hiểm</span></div>
<h3>Đọc và chuẩn hoá biểu mẫu</h3>
<p>Trích xuất thông tin từ giấy tờ định danh, hợp đồng và đơn yêu cầu bồi thường. Khôi phục dấu sau khi quét ảnh (lỗi gõ tay, lỗi máy quét) đạt <strong>97.03 %</strong> trong tình huống nhiễu nặng.</p>
</div>

<div class="ev-corner">
<div class="ev-corner-head"><span class="marker">03 · y tế</span></div>
<h3>Hồ sơ bệnh án ở lại bệnh viện</h3>
<p>Tóm tắt, phân loại và tìm kiếm bệnh án — không truyền ra ngoài máy chủ bệnh viện. Hỗ trợ cài đặt trên mạng cô lập cho khoa nghiên cứu lâm sàng.</p>
</div>

<div class="ev-corner featured">
<div class="ev-corner-head"><span class="marker">04 · điểm chung</span></div>
<h3>Dữ liệu ở lại với bạn</h3>
<p>Mọi luồng đều có thể chạy hoàn toàn ngoại tuyến. Nếu cần dùng thêm mô hình lớn trên đám mây cho một vài việc phụ, bạn cấu hình từng luồng riêng — không phải gửi tất cả ra ngoài.</p>
</div>
</div>

<div class="ev-section" id="cach-trien-khai">
<h2>§ 02 · Ba cách triển khai</h2>
<p class="lede">Cùng một mã nguồn, ba kiểu phân phối tuỳ mức độ nhạy cảm của dữ liệu và yêu cầu vận hành.</p>
</div>

<div class="ev-deploy-grid">

<div class="ev-deploy">
<div class="marker">a · tự cài</div>
<h3>Tự cài trên máy chủ của bạn</h3>
<p class="ev-deploy-summary">Cài thẳng trên Linux hoặc Docker tại trung tâm dữ liệu hoặc máy chủ phòng kỹ thuật. Phù hợp khi bạn đã có đội vận hành và quy chuẩn an ninh nội bộ.</p>
<ul class="ev-deploy-list">
<li>Có sẵn Docker Compose và Helm chart</li>
<li>Chạy được trên CPU; có GPU thì nhanh hơn 5 đến 10 lần</li>
<li>Tích hợp đăng nhập một lần (LDAP / OIDC / SAML)</li>
<li>Hỗ trợ phản hồi dưới 4 giờ trong giờ hành chính</li>
</ul>
<div class="ev-deploy-foot">Phù hợp với phần lớn doanh nghiệp 50 đến 500 người.</div>
</div>

<div class="ev-deploy ev-deploy-mid">
<div class="marker">b · vùng riêng trên đám mây</div>
<h3>Vùng riêng trên đám mây của bạn</h3>
<p class="ev-deploy-summary">Cài trong vùng mạng riêng của bạn trên AWS, Azure, GCP, Viettel IDC hoặc FPT Cloud. Bạn giữ khoá; chúng tôi cung cấp khuôn mẫu cài đặt và hỗ trợ vận hành.</p>
<ul class="ev-deploy-list">
<li>Khuôn mẫu Terraform / Pulumi cho 4 nhà cung cấp đám mây chính</li>
<li>Khoá mã hoá do bạn quản lý, chúng tôi không thấy</li>
<li>Đẩy nhật ký truy cập về hệ thống giám sát nội bộ</li>
<li>Cam kết hoạt động 99.5 %, phản hồi sự cố nghiêm trọng trong 1 giờ</li>
</ul>
<div class="ev-deploy-foot">Phù hợp với công ty công nghệ tài chính, bảo hiểm, các đơn vị đã chuẩn hoá hạ tầng đám mây.</div>
</div>

<div class="ev-deploy">
<div class="marker">c · mạng cô lập</div>
<h3>Mạng cô lập, không kết nối Internet</h3>
<p class="ev-deploy-summary">Dành cho ngân hàng nhà nước, quốc phòng, khoa nghiên cứu y tế — môi trường không có cổng ra Internet. Chúng tôi giao mô hình và phần mềm qua kênh đã được phê duyệt.</p>
<ul class="ev-deploy-list">
<li>Bộ cài ngoại tuyến trọn gói (mô hình + phần mềm)</li>
<li>Cập nhật theo lịch (quý hoặc tháng) qua phương tiện vật lý</li>
<li>Đào tạo trực tiếp 2 ngày cho đội vận hành</li>
<li>Hợp đồng hỗ trợ riêng kèm thoả thuận bảo mật</li>
</ul>
<div class="ev-deploy-foot">Đã làm việc với khách hàng yêu cầu chuẩn ISO 27001 nội bộ.</div>
</div>

</div>

<div class="ev-section">
<h2>§ 03 · Bảo mật và tuân thủ</h2>
<p class="lede">Thiết kế từ đầu cho dữ liệu nhạy cảm — không phải tính năng dán nhãn về sau.</p>
</div>

<div class="ev-compliance">

<div class="ev-compliance-row">
<div class="ev-compliance-key">Dữ liệu cá nhân</div>
<div class="ev-compliance-val">
<strong>Tuân thủ Nghị định 13/2023/NĐ-CP.</strong> Kiến trúc mặc định không truyền dữ liệu cá nhân ra hệ thống bên thứ ba. Nhật ký truy cập, cơ chế xoá dữ liệu, và trách nhiệm xử lý đều được tài liệu hoá theo từng tích hợp.
</div>
</div>

<div class="ev-compliance-row">
<div class="ev-compliance-key">Nguồn gốc phần mềm</div>
<div class="ev-compliance-val">
Không phụ thuộc thư viện kèm tệp <code>.pkl</code> / <code>.pickle</code> (vốn có thể chạy mã tuỳ ý khi nạp). Mọi mô hình bên thứ ba được cố định theo bản băm SHA256 và phiên bản; danh sách phụ thuộc và giấy phép kèm theo mỗi bản phát hành.
</div>
</div>

<div class="ev-compliance-row">
<div class="ev-compliance-key">Mã hoá và phân quyền</div>
<div class="ev-compliance-val">
Mã hoá đường truyền theo TLS 1.3 cho mọi luồng nội bộ. Phân quyền theo không gian làm việc — tài liệu được giới hạn theo phòng ban hoặc dự án. Tích hợp đăng nhập một lần (OIDC / SAML / LDAP) sẵn từ gói Doanh nghiệp Tiêu chuẩn.
</div>
</div>

<div class="ev-compliance-row">
<div class="ev-compliance-key">Nhật ký kiểm toán</div>
<div class="ev-compliance-val">
Ghi nhật ký mọi truy vấn, mọi tài liệu được tra cứu và mọi câu trả lời sinh ra — kèm bản băm của đầu vào và phiên bản mô hình đã dùng. Đẩy về Splunk, ELK hoặc Loki nội bộ qua syslog hoặc OpenTelemetry.
</div>
</div>

<div class="ev-compliance-row">
<div class="ev-compliance-key">Mã nguồn lõi</div>
<div class="ev-compliance-val">
Phần lõi <code>nom-vn</code> phát hành theo giấy phép Apache 2.0, đọc và rà soát được toàn bộ mã. Các thành phần dành riêng cho doanh nghiệp (đăng nhập một lần, xuất nhật ký kiểm toán, đầu nối Microsoft Office) phát hành theo giấy phép thương mại — tách biệt nhưng không khoá phần lõi.
</div>
</div>

<div class="ev-compliance-row">
<div class="ev-compliance-key">Chứng chỉ và lộ trình</div>
<div class="ev-compliance-val">
SOC 2 Loại I dự kiến quý 4 năm 2026; ISO 27001 nội bộ có thể đạt qua mô hình tự cài. Chúng tôi cung cấp <strong>hồ sơ năng lực bảo mật</strong> để đội an ninh của bạn rà soát theo bảng kiểm riêng — gửi yêu cầu qua thư điện tử.
</div>
</div>

</div>

<div class="ev-section">
<h2>§ 04 · Một vòng giao diện vận hành</h2>
<p class="lede">Ba màn hình đại diện cho phần dành riêng cho doanh nghiệp — phân loại rủi ro theo Luật 134/2025, quản trị giấy phép kèm dấu vết kiểm toán, và trình giám sát tác tử theo thời gian thực.</p>
</div>

<div class="ev-screens">

<figure class="ev-screen">
<img src="/screenshots/19-compliance-high-risk.png" alt="Phân loại rủi ro theo Luật 134/2025 — kết quả 'Rủi ro cao' với năm lý do tham chiếu các điều luật cụ thể." />
<figcaption>
<strong>Phân loại rủi ro theo Luật 134/2025.</strong> Mỗi câu trả lời của hệ thống chỉ rõ điều luật áp dụng (Đ8, Đ10, Đ11) với mức rủi ro tương ứng. Đầu vào dạng tự nhiên — không cần nhãn thủ công.
</figcaption>
</figure>

<figure class="ev-screen">
<img src="/screenshots/20-admin-ee-license.png" alt="Trang quản trị doanh nghiệp hiển thị tên khách hàng, hạn dùng, danh sách tính năng đang bật và 16 mục nhật ký kiểm toán có băm SHA-256." />
<figcaption>
<strong>Quản trị giấy phép và nhật ký kiểm toán.</strong> Giấy phép HMAC ký ngoại tuyến, kiểm tra cục bộ — không cần gọi máy chủ kích hoạt. Nhật ký kiểm toán băm chuỗi liên kết (SHA-256) chống chỉnh sửa.
</figcaption>
</figure>

<figure class="ev-screen">
<img src="/screenshots/18-agent-run-live.png" alt="Trình chạy tác tử hiển thị 20 sự kiện theo thời gian thực — bắt đầu, suy luận, gọi công cụ detect_language và extract_entities, kết quả thực thể." />
<figcaption>
<strong>Trình chạy tác tử theo thời gian thực.</strong> Mỗi bước (suy luận, gọi công cụ, kết quả, trả lời) được phát trực tuyến qua SSE. Mọi sự kiện đều được ghi vào nhật ký kiểm toán, kèm tên người dùng và mã phiên.
</figcaption>
</figure>

</div>

<div class="ev-section">
<h2>§ 05 · Tích hợp và lập trình</h2>
<p class="lede">REST API, thư viện Python và giao diện web đều có sẵn. Bạn chọn mô hình ngôn ngữ — không bị khoá theo nhà cung cấp.</p>
</div>

<div class="ev-integrations">

<div class="ev-integration-block">
<h3>REST API</h3>
<p>Đầy đủ điểm cuối theo chuẩn OpenAPI 3.1 cho mọi tác vụ: khôi phục dấu, sửa chính tả, đọc ảnh, sinh vector, tra cứu, hỏi đáp. Có giao diện thử trực tiếp. Xác thực qua khoá API hoặc JWT.</p>
</div>

<div class="ev-integration-block">
<h3>Thư viện Python</h3>
<p><code>pip install nom-vn</code>. Đầy đủ kiểu dữ liệu, dùng giao thức Protocol — không bị khoá vào lớp cụ thể nào. Dễ ghép vào quy trình học máy hoặc xử lý dữ liệu sẵn có.</p>
</div>

<div class="ev-integration-block">
<h3>Mô hình ngôn ngữ</h3>
<p>Mặc định Ollama (Qwen3, Llama, GPT-OSS chạy nội bộ). Có thể chuyển hướng sang Claude hoặc GPT cho tác vụ không nhạy cảm — bạn cấu hình từng luồng, không phải gửi tất cả ra ngoài.</p>
</div>

<div class="ev-integration-block">
<h3>Giao diện web</h3>
<p>Sẵn FastAPI và React, đóng gói trong <code>pip install nom-vn[chat]</code>. Có thể nhúng vào cổng nội bộ qua iframe, hoặc đổi giao diện theo thương hiệu của bạn.</p>
</div>

<div class="ev-integration-block">
<h3>Đầu nối Office</h3>
<p>Thành phần dành cho doanh nghiệp: bóc tách DOCX, XLSX, PPTX giữ nguyên đầu trang, chân trang và bảng. Sắp ra: tiện ích Outlook và đầu nối SharePoint.</p>
</div>

<div class="ev-integration-block">
<h3>Theo dõi và đo lường</h3>
<p>Dấu vết theo OpenTelemetry và chỉ số theo Prometheus. Mỗi truy vấn để lại mã tham chiếu gắn vào nhật ký để dò lỗi; ngân sách độ trễ theo từng thành phần.</p>
</div>

</div>

<div class="ev-section">
<h2>§ 06 · Các gói dịch vụ</h2>
<p class="lede">Phân theo mức cam kết hỗ trợ và mức tuỳ biến — không phải theo số lượng tính năng được mở khoá.</p>
</div>

<div class="ev-tiers">

<div class="ev-tier">
<div class="marker">cộng đồng</div>
<h3>Cộng đồng</h3>
<div class="ev-tier-price">Miễn phí · Apache 2.0</div>
<ul class="ev-tier-features">
<li>Toàn bộ phần lõi mã nguồn mở</li>
<li>Mô hình <code>nrl-ai/*</code> trên HuggingFace</li>
<li>Tài liệu và công thức triển khai</li>
<li>Hỗ trợ qua GitHub Issues</li>
</ul>
<div class="ev-tier-cta"><a href="/vi/quickstart" class="ev-tier-link">Bắt đầu →</a></div>
</div>

<div class="ev-tier ev-tier-featured">
<div class="marker">được chọn nhiều nhất</div>
<h3>Doanh nghiệp Tiêu chuẩn</h3>
<div class="ev-tier-price">Liên hệ · tính theo người dùng hoặc lượng tài liệu</div>
<ul class="ev-tier-features">
<li>Mọi thứ trong gói Cộng đồng</li>
<li>Đăng nhập một lần (OIDC / SAML / LDAP)</li>
<li>Cam kết hoạt động 99.5 %, phản hồi 4 giờ trong giờ hành chính</li>
<li>Đầu nối Office (DOCX / XLSX / PPTX nâng cao)</li>
<li>Cập nhật mô hình theo quý trên dữ liệu của bạn</li>
<li>Hỗ trợ qua thư điện tử và họp trực tuyến</li>
</ul>
<div class="ev-tier-cta"><a href="mailto:vietanh@nrl.ai?subject=N%C3%B4m%20-%20Y%C3%AAu%20c%E1%BA%A7u%20b%C3%A1o%20gi%C3%A1%20Doanh%20nghi%E1%BB%87p%20Ti%C3%AAu%20chu%E1%BA%A9n" class="ev-tier-link">Yêu cầu báo giá →</a></div>
</div>

<div class="ev-tier">
<div class="marker">tuỳ chỉnh</div>
<h3>Doanh nghiệp Mở rộng</h3>
<div class="ev-tier-price">Liên hệ · hợp đồng năm</div>
<ul class="ev-tier-features">
<li>Mọi thứ trong gói Doanh nghiệp Tiêu chuẩn</li>
<li>Triển khai mạng cô lập, đào tạo trực tiếp tại chỗ</li>
<li>Tinh chỉnh mô hình trên dữ liệu của bạn</li>
<li>Phản hồi sự cố nghiêm trọng trong 1 giờ, có gói 24/7</li>
<li>Xuất nhật ký kiểm toán cho hệ thống giám sát nội bộ</li>
<li>Thoả thuận bảo mật và xử lý dữ liệu riêng</li>
<li>Kỹ sư giải pháp được phân công riêng</li>
</ul>
<div class="ev-tier-cta"><a href="mailto:vietanh@nrl.ai?subject=N%C3%B4m%20-%20Trao%20%C4%91%E1%BB%95i%20Doanh%20nghi%E1%BB%87p%20M%E1%BB%9F%20r%E1%BB%99ng" class="ev-tier-link">Trao đổi chi tiết →</a></div>
</div>

</div>

<div class="ev-section">
<h2>§ 07 · Câu hỏi thường gặp</h2>
<p class="lede">Những điều đội an ninh và đội pháp chế thường hỏi trong buổi làm việc đầu tiên.</p>
</div>

<div class="ev-faq">

<details class="ev-faq-item">
<summary>Dữ liệu của chúng tôi có được dùng để huấn luyện mô hình không?</summary>
<p>Không. Mặc định mọi truy vấn không được lưu vượt quá phạm vi nhật ký của <em>bạn</em>. Nếu bạn muốn tinh chỉnh mô hình trên dữ liệu nội bộ, đó là một dự án riêng có hợp đồng riêng — và mô hình kết quả thuộc về bạn.</p>
</details>

<details class="ev-faq-item">
<summary>Làm sao chứng minh không có cửa sau trong mô hình?</summary>
<p>Phần lõi <code>nom-vn</code> theo giấy phép Apache 2.0 — bạn rà soát được toàn bộ mã nguồn. Mô hình do chúng tôi xuất bản (<code>nrl-ai/*</code>) ở định dạng <code>safetensors</code>, đọc nạp tất định, không có mã chạy khi nạp. Mô hình bên thứ ba được cố định theo bản băm SHA256; danh sách và lý do chọn được ghi rõ trong tài liệu của lớp bao bọc.</p>
</details>

<details class="ev-faq-item">
<summary>Có cần GPU không?</summary>
<p>Không bắt buộc. Phần lớn tác vụ chạy được trên CPU; ngân hàng và bảo hiểm thường triển khai chỉ dùng CPU vì dễ dự phòng. GPU (T4, L4, A10) tăng tốc 5 đến 10 lần cho các đợt tra cứu lớn — đáng đầu tư khi vượt 10 nghìn truy vấn mỗi ngày.</p>
</details>

<details class="ev-faq-item">
<summary>Mô hình có chạy hoàn toàn ngoại tuyến không?</summary>
<p>Có. Toàn bộ luồng tra cứu (cắt đoạn → sinh vector → tra cứu → xếp hạng lại → trả lời) chạy ngoại tuyến với mô hình nội bộ qua Ollama. Không có lệnh gọi đám mây nào trong luồng mặc định. Nếu bạn cấu hình một luồng đi ra đám mây, đó là lựa chọn rõ ràng — bật/tắt theo từng không gian làm việc.</p>
</details>

<details class="ev-faq-item">
<summary>Đội của các bạn có bao nhiêu người? Còn duy trì lâu dài không?</summary>
<p>Neural Research Lab là một đội nhỏ tại Việt Nam, dẫn dắt bởi Viet-Anh Nguyen (tác giả AnyLabeling — 3.2 nghìn sao trên GitHub). Phần lõi <code>nom-vn</code> phát triển công khai trên GitHub từ năm 2026; cam kết phát hành tối thiểu hằng quý. Hợp đồng Doanh nghiệp Mở rộng có điều khoản gửi giữ mã nguồn để bảo vệ khoản đầu tư của bạn nếu chúng tôi dừng phát triển.</p>
</details>

<details class="ev-faq-item">
<summary>So với gọi GPT-5 hoặc Claude qua API thì khác gì?</summary>
<p>Khác ở ba điểm: (1) <strong>chi phí cố định</strong>, không tăng theo lượng — phù hợp với khối lượng văn bản lớn của doanh nghiệp; (2) <strong>dữ liệu không rời máy</strong> — không gửi hợp đồng hay hồ sơ y tế ra nước ngoài; (3) <strong>tinh chỉnh riêng cho tiếng Việt</strong>, đặc biệt là khôi phục dấu, sửa chính tả và tra cứu văn bản pháp luật — những việc mà mô hình lớn trên đám mây làm được nhưng không tốt nhất.</p>
</details>

</div>

<div class="ev-cta-block" id="lien-he">

## Bước tiếp theo

Cách nhanh nhất để biết Nôm có phù hợp với bài toán của bạn không là một buổi trao đổi 30 phút. Điền vài thông tin bên dưới — chúng tôi liên hệ trong vòng một ngày làm việc với đề xuất kiến trúc cụ thể.

<div class="ev-form-wrap">

<div data-fs-success class="ev-form-success">Cảm ơn bạn đã liên hệ. Chúng tôi sẽ phản hồi qua thư điện tử trong vòng một ngày làm việc.</div>
<div data-fs-error class="ev-form-error">Có lỗi khi gửi biểu mẫu. Vui lòng thử lại hoặc viết thẳng cho <a href="mailto:vietanh@nrl.ai">vietanh@nrl.ai</a>.</div>

<form id="nom-enterprise-form" class="ev-form">

<div class="ev-form-row">
<label for="ev-form-name">Tên của bạn</label>
<input type="text" id="ev-form-name" name="name" data-fs-field required autocomplete="name" />
<span data-fs-error="name" class="ev-form-field-error"></span>
</div>

<div class="ev-form-row">
<label for="ev-form-email">Thư điện tử công ty</label>
<input type="email" id="ev-form-email" name="email" data-fs-field required autocomplete="email" placeholder="ban@congty.vn" />
<span data-fs-error="email" class="ev-form-field-error"></span>
</div>

<div class="ev-form-row">
<label for="ev-form-company">Tên doanh nghiệp</label>
<input type="text" id="ev-form-company" name="company" data-fs-field autocomplete="organization" />
<span data-fs-error="company" class="ev-form-field-error"></span>
</div>

<div class="ev-form-row-grid">

<div class="ev-form-row">
<label for="ev-form-industry">Ngành</label>
<select id="ev-form-industry" name="industry" data-fs-field>
<option value="">— chọn ngành —</option>
<option value="banking">Ngân hàng</option>
<option value="insurance">Bảo hiểm</option>
<option value="legal">Pháp chế / luật</option>
<option value="healthcare">Y tế</option>
<option value="public-sector">Khu vực nhà nước</option>
<option value="enterprise-it">Doanh nghiệp / công nghệ thông tin</option>
<option value="education">Giáo dục / nghiên cứu</option>
<option value="other">Khác</option>
</select>
</div>

<div class="ev-form-row">
<label for="ev-form-size">Quy mô</label>
<select id="ev-form-size" name="size" data-fs-field>
<option value="">— chọn quy mô —</option>
<option value="<50">Dưới 50 người</option>
<option value="50-200">50 đến 200 người</option>
<option value="200-1000">200 đến 1.000 người</option>
<option value=">1000">Trên 1.000 người</option>
</select>
</div>

</div>

<div class="ev-form-row">
<label for="ev-form-message">Bài toán bạn muốn giải</label>
<textarea id="ev-form-message" name="message" data-fs-field rows="5" required placeholder="Mô tả ngắn gọn — loại tài liệu, khối lượng, ràng buộc bảo mật, mốc thời gian"></textarea>
<span data-fs-error="message" class="ev-form-field-error"></span>
</div>

<div class="ev-form-foot">
<button type="submit" data-fs-submit-btn class="ev-btn ev-btn-brand">Gửi yêu cầu</button>
<span class="ev-form-meta">Hoặc viết thẳng cho <a href="mailto:vietanh@nrl.ai">vietanh@nrl.ai</a></span>
</div>

</form>

</div>

</div>
