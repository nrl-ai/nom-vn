# Trung tâm tuân thủ — Luật 134/2025/QH15

> nom-vn cho hệ thống AI tuân thủ Luật Trí tuệ nhân tạo Việt Nam.
> Nhật ký kiểm toán, phân loại rủi ro, hồ sơ kỹ thuật. **Mã nguồn mở.
> Chạy nội bộ. Không phụ thuộc đám mây.**

Luật 134/2025/QH15 có hiệu lực từ **01/03/2026**. Mọi hệ thống AI ở Việt
Nam phải tuân thủ trong 12-18 tháng kế tiếp:

| Lĩnh vực | Hạn tuân thủ |
|---|---|
| Y tế · Giáo dục · Tài chính | **2027-09-01** |
| Còn lại | **2027-03-01** |

`nom.compliance` là bộ công cụ Python mã nguồn mở duy nhất tới thời
điểm này đáp ứng đầu-cuối các nghĩa vụ chính của luật, sẵn bằng tiếng
Việt.

---

## Dành cho ai

### 🏦 Bên triển khai (Ngân hàng / Bệnh viện / Bảo hiểm)

Bạn chạy nom-vn cho tác vụ chịu quy định — hỏi đáp pháp luật, OCR
hợp đồng, tra cứu nội bộ. Luật yêu cầu nhật ký kiểm toán không thể
giả mạo (Đ14.1.c), báo cáo sự cố (Đ12) và minh bạch (Đ11).

**Thêm 3 dòng vào luồng đang chạy** → tuân thủ phía bên triển khai.

```python
from nom.compliance import AuditLog, AuditedLLM, AuditedRAG, RiskTier
audit = AuditLog.sqlite("audit.db", signing_key=KEY)
llm = AuditedLLM(Ollama("qwen3:8b"), audit_log=audit, risk_tier=RiskTier.MEDIUM)
rag = AuditedRAG(RAG.from_documents(...), audit_log=audit)
```

→ Đọc tiếp: [trang tác vụ](/tasks/compliance) · [tóm tắt luật](/compliance/luat-134-2025)

### 🧑‍💻 Nhà cung cấp (đơn vị phát hành mô hình + hệ thống AI cho thị trường Việt Nam)

Đ10.3 yêu cầu thông báo Bộ Khoa học và Công nghệ kèm hồ sơ phân loại
trước khi đưa hệ thống rủi ro trung bình hoặc cao vào sử dụng. Đ14.1.c
yêu cầu hồ sơ kỹ thuật cho hệ thống rủi ro cao.

**5 phút mỗi lần phát hành:** `RiskClassifier`, `ClassificationDossier`
và `TechnicalDossier` → 2 tài liệu Markdown sẵn sàng đóng dấu, kèm
trích dẫn tới điều luật.

→ Đọc tiếp: [trang tác vụ](/tasks/compliance)

### 🏢 Doanh nghiệp khởi nghiệp / vừa và nhỏ (Đ25.1 — công cụ miễn phí)

Đ25.1 quy định doanh nghiệp vừa và nhỏ được cấp **miễn phí hồ sơ mẫu
và công cụ tự đánh giá**. Nhà nước chưa chỉ định ai sản xuất công cụ
đó.

`nom.compliance.ConformityPackage` bản tối thiểu đảm nhận chức năng
này hôm nay. Khi Danh mục bắt buộc (Đ13.4) ban hành, khung mẫu sẽ tự
nâng cấp thành hồ sơ chính thức.

→ Đọc tiếp: [trang tác vụ](/tasks/compliance)

---

## Bắt đầu nhanh

```bash
pip install "nom-vn[compliance,chat]"
```

```python
import os
from nom.llm import Ollama
from nom.rag import RAG
from nom.compliance import (
    AuditLog, AuditedLLM, AuditedRAG,
    SystemSpec, RiskClassifier, RiskTier,
    TechnicalDossier,
)

# 1. Mô tả hệ thống
spec = SystemSpec(
    purpose="Trợ lý hỏi đáp pháp luật doanh nghiệp",
    sector="finance",
    automation_level="advisory",
    user_scope="org",
    handles_personal_data=True,
    affects_vulnerable_groups=False,
    can_generate_synthetic_content=False,
)

# 2. Phân loại rủi ro
result = RiskClassifier().classify(spec)
print(result.tier, result.applicable_articles)

# 3. Lắp luồng có nhật ký kiểm toán
audit = AuditLog.sqlite("audit.db", signing_key=os.environ["NOM_AUDIT_KEY"].encode())
llm = AuditedLLM(Ollama("qwen3:8b"), audit_log=audit, risk_tier=result.tier)
rag = AuditedRAG(RAG.from_documents(["contracts/*.pdf"], llm=llm), audit_log=audit)

# 4. Dùng như cũ — mọi bước được ký liên kết
ans = rag.ask("Có hợp đồng nào có điều khoản phạt vi phạm?")

# 5. Sinh hồ sơ kỹ thuật khi cần (lúc phát hành hoặc khi cơ quan kiểm tra)
TechnicalDossier.from_pipeline(
    spec=spec, classification=result, audit_log=audit,
    provider_name="ACME AI", provider_contact="legal@acme.vn",
    functional_description="...", main_input_data_types=("...",),
    risk_mitigation_measures=("...",), data_governance_notes="...",
    human_oversight_design="...",
).write("dossier.md", language="vi")
```

---

## Trạng thái phủ

| Nghĩa vụ | Điều luật | Trạng thái |
|---|---|---|
| Phân loại rủi ro 3 mức | Đ9 | ✅ Đầy đủ — quy tắc phân loại có dẫn điều luật |
| Tự phân loại + thông báo trước triển khai | Đ10 | ✅ Đầy đủ |
| Minh bạch tương tác AI | Đ11.1 | ✅ Đầy đủ |
| Đánh dấu nội dung AI sinh ra | Đ11.2, 11.4 | ✅ Theo chuẩn C2PA + tệp JSON đi kèm |
| Quản lý và báo cáo sự cố | Đ12 | ✅ Bộ ghi sự cố + dữ liệu theo Đ12.4 |
| Hồ sơ kỹ thuật + nhật ký | Đ14.1.c | ✅ Đầy đủ |
| Đánh giá sự phù hợp (rủi ro cao) | Đ13 | 🟡 Bản tối thiểu — chờ Danh mục Đ13.4 |
| Đánh giá tác động AI nhà nước | Đ27 | 🟡 Bản tối thiểu — chờ nghị định Đ27.5 |
| Đăng ký Cổng thông tin một cửa | Đ8 | ⏳ Chờ Cổng mở API công khai |

---

## Liên hệ đối tác thí điểm

`nom.compliance` đang tìm 1-2 đối tác thí điểm trong y tế, tài chính
hoặc giáo dục để cùng làm việc trước hạn 2027-09-01. Đối tác được:

- Rà soát riêng bảng quy tắc cho ngành của bạn
- Đồng tác giả bài blog tình huống thực tế
- Trích dẫn trên thẻ mô hình

Liên hệ qua [GitHub Issues](https://github.com/nrl-ai/nom-vn/issues)
hoặc kênh liên hệ của Neural Research Lab.

---

## Đọc thêm

- [Tóm tắt Luật 134/2025/QH15 dưới góc nhìn lập trình viên](/compliance/luat-134-2025)
- [`/tasks/compliance` — chi tiết kỹ thuật](/tasks/compliance)
- [GitHub — `nom.compliance`](https://github.com/nrl-ai/nom-vn/tree/main/src/nom/compliance)

> ⚠️ `nom.compliance` không phải dịch vụ pháp lý. Module này cung cấp
> công cụ kỹ thuật giúp giảm chi phí tuân thủ; trách nhiệm pháp lý
> cuối cùng (đặc biệt việc ký vào hồ sơ phân loại Đ10.3) thuộc về
> nhà cung cấp hoặc bên triển khai. Khuyến nghị rà soát bảng quy tắc
> cùng luật sư công nghệ trước khi đưa ra môi trường thật.
