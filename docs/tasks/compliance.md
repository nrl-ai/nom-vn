# Tuân thủ Luật Trí tuệ nhân tạo VN — `nom.compliance`

## TL;DR — gợi ý của chúng tôi

Cài thêm extra `[compliance]`. Wrap RAG / LLM bằng `AuditedRAG` + `AuditedLLM` để mọi lệnh gọi mô hình rơi vào nhật ký HMAC-SHA256 không thể giả mạo (Đ14.1.c). Phân loại rủi ro hệ thống bằng `RiskClassifier`; sinh hồ sơ kỹ thuật + hồ sơ phân loại bằng `TechnicalDossier` + `ClassificationDossier`. Mọi quyết định đều có cite điều luật cụ thể, không phải "model nói thế".

```bash
pip install "nom-vn[compliance,chat]"
```

## Bức tranh công khai

Tính tới 2026-05-02, không có toolkit OSS nào VN-localized cover end-to-end các nghĩa vụ Luật 134/2025/QH15. Các phương án hiện tại:

| Tool | License | VN localize | On-prem | OSS | Audit chain | Hồ sơ kỹ thuật | Kết luận |
|---|---|:---:|:---:|:---:|:---:|:---:|---|
| Asqav SDK | MIT | ❌ | ✓ | ✓ | ✓ | ❌ | General/EN; chỉ có 101 stars (2026-04-15), 1 tháng tuổi — chưa qua maturity gate. Revisit cho v0.4 |
| Microsoft Agent Governance Toolkit | MIT | ❌ | ⚠️ Azure-leaning | ✓ | ✓ | ❌ | OWASP-focused; thiên về cloud Azure |
| Bifrost | MIT | ❌ | ✓ | ✓ | ✓ | ❌ | Gateway pattern cho LLM providers; không có VN-specific risk rules |
| FPT IvyHub / IvyChat | đóng | ✓ | ✓ | ❌ | ✓ | ✓ | Enterprise platform đóng nguồn — không xem được code, không tự host được |
| **`nom.compliance`** | Apache-2.0 | ✓ | ✓ | ✓ | ✓ | ✓ | **Tự host, mã nguồn mở, VN-first; mọi quyết định cite điều luật** |

Nguồn star count + license verify trực tiếp trên GitHub 2026-05-02.

## Pipeline của chúng tôi

`nom.compliance` cover 6 nghĩa vụ pháp lý chính, mỗi cái map sang 1 submodule cite điều luật cụ thể:

| Submodule | Cite | Mục đích |
|---|---|---|
| `nom.compliance.audit` | Đ14.1.c, Đ28.3 | HMAC-SHA256 chain log; tamper-evident; export ra JSONL khi thanh tra yêu cầu |
| `nom.compliance.risk` | Đ9, Đ10, Đ14, Đ15 | Rule classifier 9 rule cite từng điều; output có reasoning + article list |
| `nom.compliance.transparency` | Đ11.1, 11.2, 11.4 | Marker "Bạn đang nói chuyện với AI" + sidecar provenance JSON cho image/audio/HTML |
| `nom.compliance.incident` | Đ3.8, Đ12 | Recorder JSONL + format payload Đ12.4 cho Cổng thông tin một cửa |
| `nom.compliance.wrappers` | Đ14.1.c, Đ14.1.e | `AuditedLLM` + `AuditedRAG` — drop-in wrap quanh `nom.llm.LLM` Protocol + `RAG.ask` |
| `nom.compliance.dossier` | Đ10, Đ13, Đ14.1.c, Đ27 | 4 generator: classification (full), technical (full), conformity (MVP), impact (MVP) |

```python
# Use case điển hình 3 dòng — deployer (90% case)
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

Ba persona điển hình:

- **Deployer** (ngân hàng / bệnh viện chạy nom-vn): wrap LLM + RAG; mở audit log; xong.
- **Provider** (anh ship model lên HF): chạy `RiskClassifier` + sinh `ClassificationDossier` + `TechnicalDossier` mỗi release.
- **SME / startup** (Đ25.1 free tool): dùng `ConformityPackage` MVP để tự đánh giá trước khi Danh mục Đ13.4 ban hành.

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

- `compliance/` (trang chủ Compliance hub) — định vị + 3 persona
- `compliance/luat-134-2025` — tóm tắt Luật 134/2025/QH15 góc developer
- [`tests/test_compliance_*`](https://github.com/nrl-ai/nom-vn/tree/main/tests) — 87 test cases cover từng điều luật
