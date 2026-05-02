# Compliance Hub — Luật 134/2025/QH15

> nom-vn cho hệ thống AI tuân thủ Luật Trí tuệ nhân tạo VN. Audit
> trail, phân loại rủi ro, hồ sơ kỹ thuật. **Mã nguồn mở. Chạy
> on-prem. Không có cloud dependency.**

Luật 134/2025/QH15 hiệu lực **01/03/2026**. Mọi hệ thống AI ở VN phải tuân thủ trong 12-18 tháng tiếp theo:

| Lĩnh vực | Deadline tuân thủ |
|---|---|
| Y tế · Giáo dục · Tài chính | **2027-09-01** |
| Còn lại | **2027-03-01** |

`nom.compliance` là toolkit Python mã nguồn mở duy nhất tới thời điểm này cover end-to-end các nghĩa vụ chính của luật, ở format VN-localized.

---

## Dành cho ai

### 🏦 Bên triển khai (Bank / Bệnh viện / Bảo hiểm)

Bạn chạy nom-vn cho regulated workload — hỏi-đáp pháp luật, OCR hợp đồng, RAG nội bộ. Luật đòi audit trail Đ14.1.c không thể giả mạo + báo cáo sự cố Đ12 + minh bạch Đ11.

**3 dòng code thêm vào pipeline hiện có** → tuân thủ deployer-side.

```python
from nom.compliance import AuditLog, AuditedLLM, AuditedRAG, RiskTier
audit = AuditLog.sqlite("audit.db", signing_key=KEY)
llm = AuditedLLM(Ollama("qwen3:8b"), audit_log=audit, risk_tier=RiskTier.MEDIUM)
rag = AuditedRAG(RAG.from_documents(...), audit_log=audit)
```

→ Đọc tiếp: [task page](/tasks/compliance) · [tóm tắt luật](/compliance/luat-134-2025)

### 🧑‍💻 Nhà cung cấp (ai ship model + hệ thống AI cho thị trường VN)

Đ10.3 yêu cầu thông báo Bộ KH&CN với hồ sơ phân loại trước khi đưa hệ thống rủi ro trung bình / cao vào sử dụng. Đ14.1.c yêu cầu hồ sơ kỹ thuật cho hệ thống rủi ro cao.

**5 phút mỗi release:** `RiskClassifier` + `ClassificationDossier` + `TechnicalDossier` → 2 tài liệu Markdown sẵn sàng đóng dấu, embed citation tới điều luật.

→ Đọc tiếp: [task page](/tasks/compliance)

### 🏢 Doanh nghiệp khởi nghiệp / SME (Đ25.1 free tool)

Đ25.1 quy định SME được cấp **miễn phí hồ sơ mẫu, công cụ tự đánh giá**. Nhà nước chưa chỉ định ai sản xuất công cụ đó.

`nom.compliance.ConformityPackage` MVP làm chức năng này hôm nay. Khi Danh mục bắt buộc Đ13.4 ban hành, bộ skeleton tự nâng cấp thành hồ sơ chính thức.

→ Đọc tiếp: [task page](/tasks/compliance)

---

## Quick start

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
    purpose="Trợ lý hỏi-đáp pháp luật doanh nghiệp",
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

# 3. Wire audited pipeline
audit = AuditLog.sqlite("audit.db", signing_key=os.environ["NOM_AUDIT_KEY"].encode())
llm = AuditedLLM(Ollama("qwen3:8b"), audit_log=audit, risk_tier=result.tier)
rag = AuditedRAG(RAG.from_documents(["contracts/*.pdf"], llm=llm), audit_log=audit)

# 4. Dùng như cũ — mọi step được chain-sign
ans = rag.ask("Có hợp đồng nào có điều khoản phạt vi phạm?")

# 5. Sinh hồ sơ kỹ thuật khi cần (release / audit)
TechnicalDossier.from_pipeline(
    spec=spec, classification=result, audit_log=audit,
    provider_name="ACME AI", provider_contact="legal@acme.vn",
    functional_description="...", main_input_data_types=("...",),
    risk_mitigation_measures=("...",), data_governance_notes="...",
    human_oversight_design="...",
).write("dossier.md", language="vi")
```

---

## Trạng thái coverage

| Nghĩa vụ | Điều luật | Trạng thái |
|---|---|---|
| Phân loại rủi ro 3 mức | Đ9 | ✅ Full — rule classifier cite article |
| Self-classify + thông báo trước triển khai | Đ10 | ✅ Full |
| Minh bạch tương tác AI | Đ11.1 | ✅ Full |
| Đánh dấu nội dung AI sinh | Đ11.2, 11.4 | ✅ C2PA-aligned + sidecar JSON |
| Quản lý + báo cáo sự cố | Đ12 | ✅ Recorder + Đ12.4 payload |
| Hồ sơ kỹ thuật + nhật ký | Đ14.1.c | ✅ Full |
| Đánh giá sự phù hợp (high-risk) | Đ13 | 🟡 MVP — chờ Danh mục Đ13.4 |
| Đánh giá tác động AI nhà nước | Đ27 | 🟡 MVP — chờ nghị định Đ27.5 |
| Đăng ký Cổng thông tin một cửa | Đ8 | ⏳ chờ portal API public |

---

## Liên hệ pilot / design partner

`nom.compliance` đang tìm 1-2 design partner ở y tế / tài chính / giáo dục để cùng pilot trước deadline 2027-09-01. Bạn được:

- Review riêng rule table cho ngành của bạn
- Co-authorship trên blog post case-study
- Citation trên model card

Liên hệ qua [GitHub Issues](https://github.com/nrl-ai/nom-vn/issues) hoặc kênh contact của Neural Research Lab.

---

## Đọc thêm

- [Tóm tắt Luật 134/2025/QH15 góc developer](/compliance/luat-134-2025)
- [`/tasks/compliance` — chi tiết kỹ thuật](/tasks/compliance)
- [GitHub — `nom.compliance`](https://github.com/nrl-ai/nom-vn/tree/main/src/nom/compliance)

> ⚠️ `nom.compliance` không phải dịch vụ pháp lý. Module cung cấp công cụ kỹ thuật giảm chi phí tuân thủ; trách nhiệm pháp lý cuối cùng (đặc biệt việc ký vào hồ sơ phân loại Đ10.3) thuộc về nhà cung cấp / bên triển khai. Khuyến nghị rà soát rule table với luật sư công nghệ trước khi ship production.
