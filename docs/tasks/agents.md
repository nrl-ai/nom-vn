# Multi-agent — chạy nhiều tác tử AI phối hợp

## TL;DR — gợi ý của chúng tôi

Mô-đun `nom.agents` cung cấp **6 kiểu tác tử** (Single, Chain, Route,
Parallel, Voting, OrchestratorWorkers, EvaluatorOptimizer) chạy được
trên bất kỳ mô hình ngôn ngữ nào theo giao thức `nom.llm.LLM`. Mọi
lượt gọi mô hình đều đi qua `AuditedLLM` để ghi vào nhật ký kiểm
toán theo Đ14.1.c — không có cửa hậu nào bỏ qua được lớp này.

Bốn công cụ tích hợp sẵn (`RAGTool`, `PythonEvalTool`, `HTTPGetTool`,
`FileReadTool`) đủ cho hầu hết nhu cầu "trả lời từ tài liệu + thực
hiện hành động". Chọn kiểu tác tử theo bài toán: dùng `SingleAgent`
cho 90 % trường hợp; chỉ chuyển sang các kiểu phức tạp hơn khi thật
sự cần phân rã, chạy song song hoặc tự đánh giá.

## Vì sao xây thuần thay vì dùng khung làm việc khác

Anthropic (tác giả của Claude) khuyến nghị: *"Những triển khai
thành công nhất không dùng khung làm việc phức tạp hay thư viện
chuyên biệt"* — các khung sẵn có thường thêm cấu trúc khiến mã khó
truy vết và phụ thuộc nặng. `nom.agents` xây thuần, bề mặt gọn,
mọi lượt gọi mô hình đều ghi vào nhật ký kiểm toán; phù hợp với
yêu cầu truy vết Luật 134/2025 và chính sách bảo mật của ngân
hàng / y tế.

## Cách dùng

`nom.agents.protocol` định nghĩa 3 giao thức nhỏ: `Tool` (hàm gọi
được kèm JSON-Schema), `Agent` (`run(task) -> AgentResult`), `Trace`
(nhật ký sự kiện chỉ ghi-thêm). 6 kiểu tác tử lồng ghép tự do —
một `Orchestrator` có thể chuyển hướng cho `Single`, công cụ của
`Single` lại có thể bao một `Chain`. Mỗi kiểu tác tử nằm gọn trong
một file ≤200 dòng.

```python
from nom.llm import Ollama
from nom.compliance import AuditedLLM, AuditLog, RiskTier
from nom.rag import RAG
from nom.agents import SingleAgent, RAGTool

rag = RAG.from_documents(["docs.pdf"])
audit = AuditLog.sqlite("audit.db", signing_key=key)
llm = AuditedLLM(Ollama("qwen3:8b"), audit_log=audit, risk_tier=RiskTier.MEDIUM)

agent = SingleAgent(
    name="advisor",
    llm=llm,
    tools=(RAGTool(rag, name="search"),),
)
result = agent.run("Câu hỏi của bạn?")
print(result.output)
```

## Các "công thức" tác tử có sẵn

`nom.agents.recipes` đóng gói 4 mẫu sẵn dùng — nhà triển khai gọi
một dòng là chạy:

| Công thức | Ghép từ | Dùng cho |
|---|---|---|
| `vn_doc_analyser(llm)` | nhận diện ngôn ngữ + nhận diện thực thể + cảm xúc | Phân tích văn bản đầu vào (góp ý, hồ sơ) |
| `legal_qa(rag, llm)` | `RAGTool` + lời nhắc bắt buộc trích dẫn | Hỏi-đáp pháp luật có dẫn nguồn |
| `deep_research(llm, search_tools)` | `OrchestratorWorkers` + nhân viên tra cứu | Nghiên cứu sâu nhiều nguồn |
| `compliance_screener(inner)` | Lớp che dữ liệu cá nhân quanh tác tử | Bọc bất kỳ tác tử nào để chặn / che dữ liệu cá nhân trước khi gọi mô hình |

Bản trình diễn chạy được không cần Ollama: `examples/recipes_demo.py`.

## API HTTP và truyền sự kiện thời gian thực (`agent2ui`)

Hàm `nom.agents_api.register_agent_routes(app, agents=…)` thêm 2
điểm cuối vào ứng dụng FastAPI:

- `POST /api/agents/{name}/run` — đồng bộ, trả về `output` và `trace`
- `GET /api/agents/{name}/stream?task=…` — luồng sự kiện SSE; mỗi
  sự kiện là một bước trong nhật ký (`start`, `think`, `tool_call`,
  `tool_result`, `final`, `end`)

Giao diện đăng ký luồng SSE để hiển thị tác tử đang suy luận, gọi
công cụ và trả lời theo thời gian thực.

## MCP — Model Context Protocol

Cả 4 công cụ tích hợp sẵn tự động trở thành công cụ MCP qua lệnh
`nom mcp-serve`:

```bash
nom mcp-serve --include nlp,builtin,integrations
# Cấu hình lệnh này trong Claude Desktop / Cursor; chương trình
# khách tự khám phá danh sách công cụ và gọi qua JSON-RPC stdio.
```

Theo chiều ngược lại, tác tử trong Nôm có thể tiêu thụ máy chủ
MCP bên ngoài qua `nom.mcp.MCPClient` cộng với `make_remote_tools()` —
mỗi công cụ ở xa hiện ra như một công cụ cục bộ.

## Bẫy thường gặp

- **Ngân sách số bước mặc định** đủ cho phần lớn truy hồi tài liệu
  kèm 1-2 lần gọi công cụ kế tiếp. Tăng ngân sách khi tác tử cần
  khám phá nhiều bước (ví dụ nghiên cứu sâu).
- **Công cụ trả về `ToolError`** thì vòng lặp tác tử tự thử lại;
  các ngoại lệ khác sẽ truyền tiếp ra ngoài. Hãy phân biệt rõ "lỗi
  mong đợi có thể tự sửa" và "lỗi bất ngờ phải dừng".
- **Mô hình đôi khi trả về JSON kèm dấu fence Markdown** — thư
  viện có cơ chế khôi phục, nhưng lời nhắc gọn rõ vẫn cho kết quả
  ổn định hơn.

## Đọc thêm

- [Building Effective Agents — Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- `examples/recipes_demo.py` — bản trình diễn chạy được 4 công thức
