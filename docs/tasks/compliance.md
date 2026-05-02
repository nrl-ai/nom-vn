# Tuân thủ Luật Trí tuệ nhân tạo VN — `nom.compliance`

## Tóm tắt — gợi ý của chúng tôi

Cài thêm `pip install "nom-vn[compliance]"`. Bao quanh `RAG` / `LLM` của bạn bằng `AuditedRAG` + `AuditedLLM` để mọi lệnh gọi mô hình rơi vào nhật ký HMAC-SHA256 không thể giả mạo (Đ14.1.c). Phân loại rủi ro hệ thống bằng `RiskClassifier`; sinh hồ sơ kỹ thuật + hồ sơ phân loại bằng `TechnicalDossier` + `ClassificationDossier`. Mọi quyết định đều dẫn nguồn điều luật cụ thể, không phải "mô hình nói thế".

```bash
pip install "nom-vn[compliance,chat]"
```

## Bức tranh công khai

Tính đến 2026-05-02, không có bộ công cụ mã nguồn mở nào tiếng Việt đáp ứng đầu-cuối các nghĩa vụ Luật 134/2025/QH15. Các phương án hiện có:

| Bộ công cụ | Giấy phép | Tiếng Việt | Tự cài đặt nội bộ | Mã nguồn mở | Chuỗi nhật ký | Hồ sơ kỹ thuật | Kết luận |
|---|---|:---:|:---:|:---:|:---:|:---:|---|
| Asqav SDK | MIT | ❌ | ✓ | ✓ | ✓ | ❌ | Tổng quát, tiếng Anh; chỉ 101 sao GitHub (2026-04-15), khoảng 1 tháng tuổi — chưa đủ trưởng thành. Xem lại ở v0.4. |
| Microsoft Agent Governance Toolkit | MIT | ❌ | ⚠️ thiên về Azure | ✓ | ✓ | ❌ | Tập trung OWASP; thiên về đám mây Azure. |
| Bifrost | MIT | ❌ | ✓ | ✓ | ✓ | ❌ | Mẫu gateway cho LLM; không có quy tắc rủi ro theo luật Việt Nam. |
| FPT IvyHub / IvyChat | đóng | ✓ | ✓ | ❌ | ✓ | ✓ | Nền tảng doanh nghiệp đóng nguồn — không xem được mã, không tự cài đặt được. |
| **`nom.compliance`** | Apache-2.0 | ✓ | ✓ | ✓ | ✓ | ✓ | **Tự cài đặt nội bộ, mã nguồn mở, ưu tiên tiếng Việt; mọi quyết định dẫn nguồn điều luật.** |

Số sao và giấy phép xác minh trực tiếp trên GitHub ngày 2026-05-02.

## Quy trình của chúng tôi

`nom.compliance` đáp ứng 6 nghĩa vụ pháp lý chính; mỗi mô-đun con dẫn nguồn điều luật cụ thể:

| Mô-đun con | Điều luật | Mục đích |
|---|---|---|
| `nom.compliance.audit` | Đ14.1.c, Đ28.3 | Chuỗi nhật ký HMAC-SHA256 không thể giả mạo; xuất JSONL khi cơ quan kiểm tra yêu cầu. |
| `nom.compliance.risk` | Đ9, Đ10, Đ14, Đ15 | Bộ phân loại theo quy tắc với 9 quy tắc dẫn nguồn từng điều; kết quả kèm lập luận và danh sách điều luật áp dụng. |
| `nom.compliance.transparency` | Đ11.1, 11.2, 11.4 | Câu thông báo "Bạn đang nói chuyện với AI" + tệp đi kèm JSON đánh dấu nguồn gốc cho ảnh / âm thanh / HTML. |
| `nom.compliance.incident` | Đ3.8, Đ12 | Bộ ghi sự cố JSONL + định dạng dữ liệu theo Đ12.4 để gửi Cổng thông tin một cửa. |
| `nom.compliance.wrappers` | Đ14.1.c, Đ14.1.e | `AuditedLLM` + `AuditedRAG` — lớp bao thay thế trực tiếp cho `nom.llm.LLM` Protocol và `RAG.ask`. |
| `nom.compliance.dossier` | Đ10, Đ13, Đ14.1.c, Đ27 | 4 bộ sinh: phân loại (đầy đủ), kỹ thuật (đầy đủ), đánh giá sự phù hợp (bản tối thiểu), đánh giá tác động (bản tối thiểu). |

```python
# Tình huống dùng 3 dòng — bên triển khai (90% trường hợp)
import os
from nom.llm import Ollama
from nom.rag import RAG
from nom.compliance import AuditLog, AuditedLLM, AuditedRAG, RiskTier

audit = AuditLog.sqlite("audit.db", signing_key=os.environ["NOM_AUDIT_KEY"].encode())
llm = AuditedLLM(Ollama("qwen3:8b"), audit_log=audit, risk_tier=RiskTier.MEDIUM)
rag = AuditedRAG(RAG.from_documents(["contracts/*.pdf"], llm=llm), audit_log=audit)
```

```python
# Khi thanh tra Bộ KH&CN đến (Đ28.3)
audit.verify().raise_if_tampered()
audit.export("evidence.jsonl",
             since="2026-04-02T00:00:00.000000Z",
             until="2026-05-02T23:59:59.999999Z")
```

Ba kiểu người dùng tiêu biểu:

- **Bên triển khai** (ngân hàng / bệnh viện chạy nom-vn): bao `LLM` + `RAG` qua `AuditedLLM` / `AuditedRAG`; mở nhật ký kiểm toán; xong.
- **Nhà cung cấp** (đơn vị phát hành mô hình lên Hugging Face): chạy `RiskClassifier` + sinh `ClassificationDossier` + `TechnicalDossier` mỗi lần phát hành.
- **Doanh nghiệp khởi nghiệp / vừa và nhỏ** (Đ25.1 — công cụ miễn phí): dùng `ConformityPackage` bản tối thiểu để tự đánh giá trước khi Danh mục Đ13.4 ban hành.

## Trạng thái — đã build vs đang chờ nghị định

| Nghĩa vụ | Điều | Trạng thái v0.3 | Trạng thái khi nghị định ra |
|---|---|---|---|
| Phân loại rủi ro 3 mức | Đ9.1 | ✅ rule classifier cite article | + LLM tie-breaker khi Đ9.3 chi tiết |
| Tự thông báo + dossier | Đ10 | ✅ `ClassificationDossier` | Adapter sang format Bộ KH&CN khi Đ10.7 ra |
| Minh bạch tương tác | Đ11.1 | ✅ `interaction_notice()` | + format theo Đ11.6 |
| Đánh dấu nội dung tổng hợp | Đ11.2 | ✅ C2PA-aligned + nom-sidecar JSON | Translator → format chính thức (Đ11.6) |
| Báo cáo sự cố | Đ12 | ✅ `IncidentRecorder` + payload Đ12.4 | Adapter API Cổng thông tin một cửa khi public |
| Hồ sơ kỹ thuật + nhật ký | Đ14.1.c | ✅ `TechnicalDossier` + `AuditLog` | — |
| Đánh giá sự phù hợp | Đ13 | 🟡 MVP skeleton (`ConformityPackage`) | Full khi PM ban hành Danh mục Đ13.4 |
| Đánh giá tác động AI nhà nước | Đ27 | 🟡 MVP skeleton (`ImpactAssessment`) | Full khi nghị định Đ27.5 ra |
| Đăng ký Cổng thông tin một cửa | Đ8, Đ10.3 | ⏳ chờ portal API public | `nom.compliance.registry` v0.4 |

Status hiện tại: 6/9 đầy đủ, 2/9 MVP skeleton, 1/9 chờ portal API. Đủ để self-assessment + tự host hôm nay; full compliance khi 3 nghị định còn lại ban hành.

## Tuyên bố đáng tin

`nom.compliance` không phải dịch vụ pháp lý. Module cung cấp **công cụ kỹ thuật** để giảm chi phí tuân thủ; trách nhiệm pháp lý cuối cùng (đặc biệt ký vào hồ sơ phân loại Đ10.3) thuộc về nhà cung cấp / bên triển khai. Khuyến nghị: rà soát rule table trong `nom.compliance.risk.rules` và customize cho ngành cụ thể với một luật sư công nghệ trước khi ship production.

## Tham khảo thêm

- [Trung tâm tuân thủ](/compliance/) — định vị + 3 kiểu người dùng
- [Tóm tắt Luật 134/2025/QH15](/compliance/luat-134-2025) — góc nhìn lập trình viên
- [`tests/test_compliance_*`](https://github.com/nrl-ai/nom-vn/tree/main/tests) — hơn 100 ca kiểm thử bao phủ từng điều luật
