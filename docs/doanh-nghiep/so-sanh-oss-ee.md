---
title: So sánh Cộng đồng vs Doanh nghiệp
description: Bản Cộng đồng (Apache 2.0) và bản Doanh nghiệp khác nhau ở đâu — đối chiếu từng tính năng, lý do tách bản, và đường nâng cấp.
---

<!-- markdownlint-disable-next-line MD025 -->
# So sánh: bản Cộng đồng vs bản Doanh nghiệp


![Bảng so sánh hai bản](/screenshots/14-compare-oss-ee-top.png)

Nôm phát hành theo mô hình **lõi mở**: phần lõi mã nguồn mở giấy
phép Apache 2.0 dùng được cho sản xuất; các tính năng cần khi
triển khai cho doanh nghiệp lớn (>50 người dùng, nhiều bộ phận,
có cán bộ kiểm toán) thuộc gói thương mại.

Bản Cộng đồng **không bị cắt bớt** để ép mua. Một lập trình viên
cá nhân ở Việt Nam tự cài được toàn bộ ngăn xếp RAG + tác tử +
tuân thủ, miễn phí, vĩnh viễn. Bản Doanh nghiệp giải quyết "vấn đề
công ty 200 người" — không thay thế bản Cộng đồng, mà gắn thêm các
plugin tích hợp với hệ thống nội bộ qua các điểm cắm (Protocol)
đã có sẵn.

## Tóm tắt

| Tình huống | Bản nào? |
|---|---|
| Lập trình viên cá nhân, dự án nhỏ, tự nghiên cứu | **Cộng đồng** |
| Đội 5-50 người, một dự án, một mô hình ngôn ngữ | **Cộng đồng** |
| Doanh nghiệp >50 người, nhiều bộ phận, đăng nhập một lần | **Doanh nghiệp** |
| Ngành tài chính / y tế / công có cán bộ kiểm toán | **Doanh nghiệp** |
| Triển khai mạng cô lập (không kết nối Internet) | **Doanh nghiệp** |
| Cần tích hợp Microsoft 365 / SharePoint / Teams | **Doanh nghiệp** |

## Bảng đối chiếu chi tiết

### Lõi AI (RAG + mô hình ngôn ngữ + tác tử + xử lý ngôn ngữ)

| Tính năng | Cộng đồng | Doanh nghiệp |
|---|---|---|
| RAG: cắt đoạn → vector hoá → truy hồi → xếp lại → trả lời | ✅ Đầy đủ | ✅ |
| Đa nền tảng mô hình ngôn ngữ (Ollama / vLLM / OpenAI / Anthropic / llama.cpp) | ✅ | ✅ |
| Tác tử đa thành phần (6 kiểu theo Anthropic) | ✅ Đầy đủ | ✅ |
| Công thức tác tử (`legal_qa`, `vn_doc_analyser`, `deep_research`, `compliance_screener`) | ✅ | ✅ |
| Cầu nối MCP (máy chủ + chương trình khách, stdio + HTTP) | ✅ | ✅ |
| Bộ tích hợp MCP không cần khoá truy cập (FileGlob, JSON, CurrentTime) | ✅ | ✅ |
| Xử lý ngôn ngữ: nhận diện thực thể + cảm xúc + nhận diện ngôn ngữ | ✅ | ✅ |
| Khôi phục dấu (HuggingFace + mô hình ngôn ngữ + rule-based) | ✅ | ✅ |
| Sửa chính tả tiếng Việt | ✅ | ✅ |
| Nhận dạng ký tự quang học (OCR) — Tesseract `vie` | ✅ | ✅ |
| Tách từ và tách câu | ✅ | ✅ |
| Hàng đợi tác vụ nền (SQLite) | ✅ | ✅ |
| Truyền sự kiện thời gian thực (`agent2ui`) | ✅ | ✅ |

### Tuân thủ — Luật 134/2025 + Nghị định 13/2023

| Tính năng | Cộng đồng | Doanh nghiệp |
|---|---|---|
| Chuỗi nhật ký kiểm toán ký HMAC-SHA256 (Đ14.1.c, Đ28.3) | ✅ | ✅ |
| Lớp bao bọc `AuditedLLM` / `AuditedRAG` | ✅ | ✅ |
| Phân loại rủi ro 3 mức (Đ9, Đ10) | ✅ | ✅ |
| Hồ sơ kỹ thuật (Đ14.1.c) | ✅ | ✅ |
| Hồ sơ phân loại (Đ10) | ✅ | ✅ |
| Hồ sơ tự đánh giá phù hợp (Đ13) — bản tối thiểu | ✅ tối thiểu | ✅ Đầy đủ theo ngành (ngân hàng, y tế, dịch vụ công) |
| Đánh giá tác động (Đ27) — bản tối thiểu | ✅ tối thiểu | ✅ Đầy đủ theo ngành |
| Thông báo minh bạch + đánh dấu nội dung (Đ11) | ✅ | ✅ |
| Ghi nhận sự cố (Đ12) | ✅ Cục bộ | ✅ Cục bộ + đẩy về trung tâm vận hành an ninh qua syslog / HEC |
| Phát hiện thông tin cá nhân — regex Việt Nam (CCCD/CMND/MST/STK/SĐT/email) | ✅ | ✅ |
| Phát hiện thông tin cá nhân — tên người + địa chỉ tiếng Việt | — | ✅ `nom_ee.privacy.VNAdvancedPIIDetector` |
| Che thông tin cá nhân — mask / hash / drop | ✅ | ✅ |
| Che thông tin cá nhân — token có thể giải ngược (kho mã hoá theo tenant) | — | ✅ `nom_ee.privacy.TokenizeRedactor` |
| Xuất nhật ký kiểm toán (JSONL) | ✅ | ✅ |
| Đẩy nhật ký kiểm toán — Splunk HEC / Elasticsearch / Loki / OTLP | — | ✅ `nom_ee.audit_forward.*` |

### Định danh và phân quyền

| Tính năng | Cộng đồng | Doanh nghiệp |
|---|---|---|
| Khoá mang theo (`NOM_AUTH_TOKEN`) | ✅ | ✅ |
| Đăng nhập một lần qua OIDC (Keycloak / Azure AD / Okta / ADFS) | — | ✅ |
| Đăng nhập một lần qua SAML 2.0 | — | ✅ |
| LDAP / Active Directory | — | ✅ |
| Phân quyền theo vai trò — kiểu cho-tất-cả / bảng tĩnh | ✅ | ✅ |
| Phân quyền nhiều tổ chức (tenant + người dùng + vai trò) | — | ✅ |
| Quy trách nhiệm từng người dùng trong nhật ký kiểm toán (Đ14.1.c) | ✅ điểm cắm có sẵn | ✅ Tự động qua trường `sub` của OIDC |
| Bảng quản trị khoá API | — | ✅ |

### Triển khai

| Tính năng | Cộng đồng | Doanh nghiệp |
|---|---|---|
| `nom serve` đơn (FastAPI + SQLite) | ✅ | ✅ |
| Ảnh Docker (mức Solo) | ✅ | ✅ |
| Helm chart cho cụm nhỏ — K3s / docker-compose | ✅ | ✅ |
| Helm chart cho cụm lớn — tự co giãn, Postgres HA, cụm vLLM | — | ✅ |
| Mẫu Terraform / Pulumi (AWS, Azure, GCP, Viettel IDC, FPT Cloud) | — | ✅ |
| Bộ cài cho mạng cô lập (mô hình + phần mềm) | ✅ tự đóng gói | ✅ Bộ ký số do NRL phát theo lịch |
| Nhiều tổ chức trên cùng một schema | ✅ | ✅ |
| Mỗi tổ chức một schema / một CSDL riêng | — | ✅ |

### Tích hợp

| Tính năng | Cộng đồng | Doanh nghiệp |
|---|---|---|
| Bóc tách file (PDF / DOCX / XLSX / PPTX / ảnh) | ✅ | ✅ |
| Máy chủ MCP (stdio + HTTP) | ✅ | ✅ |
| Bộ tích hợp MCP không cần khoá truy cập | ✅ FileGlob / JSON / CurrentTime | ✅ |
| Đầu nối Microsoft Office (DOCX / XLSX / PPTX nâng cao) | ✅ bóc tách cơ bản | ✅ Dịch giữ định dạng, dữ liệu siêu cấp |
| Outlook / Teams / SharePoint / OneDrive | — | ✅ |
| GitHub PR / issue / Slack / Linear | — | ✅ (sắp ra) |
| Adapter cho LangChain / Pydantic AI / Google ADK | ✅ tài liệu | ✅ tài liệu |

### Giao diện

| Tính năng | Cộng đồng | Doanh nghiệp |
|---|---|---|
| Khu chơi chat và RAG | ✅ | ✅ |
| Khu chơi công cụ văn bản (khôi phục dấu, tách từ, chuẩn hoá, bỏ dấu) | ✅ | ✅ |
| Trang xem tác tử chạy theo thời gian thực | 🚧 đang phát triển | ✅ |
| Bảng tuân thủ — xem / xuất hồ sơ, biểu mẫu sự cố | 🚧 đang phát triển (cơ bản) | ✅ Đầy đủ theo ngành |
| Bảng quản trị — người dùng, vai trò, khoá API, lưu lượng, tra cứu nhật ký | — | ✅ |

### Hỗ trợ và cam kết

| Tính năng | Cộng đồng | Doanh nghiệp Tiêu chuẩn | Doanh nghiệp Mở rộng |
|---|---|---|---|
| Mã nguồn lõi | Apache 2.0 | Apache 2.0 | Apache 2.0 |
| Mã nguồn doanh nghiệp | — | Bản quyền thương mại (riêng tư) | Bản quyền + gửi giữ mã nguồn |
| Cập nhật | Bản phát hành công khai | Cam kết hằng quý | Cam kết hằng quý + bản vá nóng |
| Cam kết hỗ trợ | Hỏi đáp công khai, không cam kết | 4 giờ trong giờ hành chính | 1 giờ với sự cố nghiêm trọng, có gói 24/7 |
| Đào tạo | Tài liệu công khai | Thư điện tử + họp trực tuyến | Đào tạo trực tiếp 2 ngày |
| Hợp đồng bảo mật | — | Thoả thuận bảo mật chuẩn | Thoả thuận xử lý dữ liệu + gửi giữ mã + thoả thuận riêng |
| Chứng chỉ doanh nghiệp | — | SOC 2 (dự kiến quý 4 năm 2026) | SOC 2 + hỗ trợ rà soát ISO 27001 |

## Tại sao tách hai bản

Phần lõi của Nôm — chuỗi nhật ký kiểm toán, hồ sơ tuân thủ, phân
loại rủi ro, tác tử, RAG, xử lý ngôn ngữ — đều ở bản Cộng đồng.
Đây là những thứ doanh nghiệp có yêu cầu tuân thủ **bắt buộc phải
có** trên giấy; chúng tôi không bán riêng phần này.

Bản Doanh nghiệp gắn thêm các tính năng cần khi vận hành ở quy mô:
đăng nhập một lần, phân quyền nhiều tổ chức, đẩy nhật ký về trung
tâm vận hành an ninh, bảng quản trị, các đầu nối Microsoft 365 /
Office. Đây là những phần một lập trình viên cá nhân không cần
nhưng một doanh nghiệp 200 người không thể thiếu.

Chuyển từ Cộng đồng sang Doanh nghiệp không cần sửa mã: cài thêm
gói plugin và đặt giấy phép, các thành phần tự nhận diện và bật.

## Đường nâng cấp

```text
Cá nhân  →  Đội nhỏ (5-50 người)  →  Doanh nghiệp  →  Mạng cô lập
Cộng đồng     Cộng đồng                Doanh nghiệp    Doanh nghiệp
```

Mọi bước nâng cấp **giữ nguyên dữ liệu**: chuỗi nhật ký kiểm toán
đã ghi vẫn xác minh được sau khi nâng cấp; không gian làm việc và
tài liệu di chuyển qua `nom export` / `nom import`; cấu hình mô
hình ngôn ngữ không đổi.

## Liên hệ

[Đặt lịch trao đổi 30 phút](/doanh-nghiep/#lien-he) · `vietanh@nrl.ai`
