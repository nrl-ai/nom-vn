# Multi-agent runtime

## TL;DR — gợi ý của chúng tôi

`nom.agents` cung cấp 6 mẫu agent (Single, Chain, Route, Parallel,
Voting, OrchestratorWorkers, EvaluatorOptimizer) chạy trên bất kỳ
LLM nào theo `nom.llm.LLM` Protocol, mọi lệnh gọi LLM đi qua
`AuditedLLM` để vào nhật ký kiểm toán Đ14.1.c. Built-in tools
(RAGTool, PythonEvalTool, HTTPGetTool, FileReadTool) đủ cho phần
lớn use case "trả lời từ tài liệu + thực hiện hành động". Chọn mẫu
theo bài toán: `SingleAgent` cho 90% case, các mẫu phức tạp hơn khi
cần phân rã / song song / tự đánh giá.

## Bức tranh công khai

| Framework | License | Format | Pickle? | Trace audit | Kết luận |
|---|---|---|---|---|---|
| LangChain / LangGraph | MIT | Mixed | **Có** (cache, checkpoint) | Có (LangSmith cloud) | Bỏ qua — vi phạm policy không-pickle, breaking-change ~2 tuần |
| Pydantic AI | MIT | Pure-Python | Không | OTel | Học pattern (typed Agent) — không phụ thuộc trực tiếp |
| Google ADK | Apache 2.0 | Mixed | Mixed | OTel | Dep tree quá nặng để embed; học workflow primitive |
| OpenAI Agents SDK | MIT | Pure-Python | Không | OpenAI cloud (default) | Pre-1.0, default tracing về cloud OpenAI — bỏ qua |
| AutoGen | CC-BY-4.0 | Pure-Python | Không | Optional OTel | **Maintenance mode** từ 2026 — bỏ qua |
| CrewAI | MIT | Pure-Python | Không | PostHog (default-on) | PostHog default-on = data egress — bỏ qua |
| Smolagents | Apache 2.0 | Pure-Python | 4 hits | OpenInference | Code-as-action sai cho compliance — học minimalism |

Anthropic (tác giả Claude) tổng kết: *"the most successful
implementations weren't using complex frameworks or specialized
libraries"*. Chúng tôi xây native — surface ~1.5k LOC, mọi LLM call
đi qua `AuditedLLM`.

## Pipeline của chúng tôi

`nom.agents.protocol` định nghĩa 3 Protocol nhỏ: `Tool` (callable +
JSON-Schema), `Agent` (`run(task) -> AgentResult`), `Trace`
(append-only event log). 6 mẫu pattern composable — orchestrator có
thể route đến single, single's tool có thể bao chain. Mỗi pattern
độc lập trong file ≤200 dòng.

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

## Agent recipes — factories có sẵn

`nom.agents.recipes` ship 4 mẫu sẵn dùng — operator gọi một dòng:

| Recipe | Compose | Use case |
|---|---|---|
| `vn_doc_analyser(llm)` | Lang detect + NER + sentiment | Phân tích văn bản đầu vào (feedback, hồ sơ) |
| `legal_qa(rag, llm)` | RAGTool + cite-first prompt | Hỏi-đáp pháp luật có trích dẫn |
| `deep_research(llm, search_tools)` | OrchestratorWorkers + searcher | Nghiên cứu sâu đa nguồn |
| `compliance_screener(inner)` | PII redact wrapper | Bọc bất kỳ agent nào để chặn / che PII trước LLM |

Demo chạy được không cần Ollama: `examples/recipes_demo.py`.

## HTTP & SSE — agent2ui

`nom.agents_api.register_agent_routes(app, agents=…)` thêm 2 endpoint
vào FastAPI app:

- `POST /api/agents/{name}/run` — đồng bộ, trả `output` + `trace`
- `GET /api/agents/{name}/stream?task=…` — SSE, mỗi event là một
  trace step (start, think, tool_call, tool_result, final, end)

UI subscribe SSE → render thời gian thực việc agent suy luận / gọi
tool / trả lời. Đây là protocol "agent2ui" — UI viewer page sẽ ship
trong wave kế tiếp.

## MCP — Model Context Protocol

Tất cả 4 built-in tool tự động trở thành MCP tool qua `nom mcp-serve`:

```bash
nom mcp-serve --include nlp,builtin,integrations
# Trong Claude Desktop / Cursor config, thêm command này; client tự
# discover các tool và gọi qua JSON-RPC stdio.
```

Theo chiều ngược lại, agents trong nom có thể consume MCP server bên
ngoài qua `nom.mcp.MCPClient` + `make_remote_tools()` — mỗi remote
tool xuất hiện như một local Tool.

## Đo và benchmark

OSS suite hiện có 691 test, trong đó 32 test cho `nom.agents` +
recipes. Patterns được verify với scripted LLM (deterministic) +
smoke test chạy được với Ollama local.

Benchmark thực trên Ollama qwen3:8b: TBD — sẽ thêm khi có corpus
chuẩn (tương tự benchmarks/rag/ pattern).

## Bẫy thường gặp

- **Không dùng `from __future__ import annotations` trong file route
  FastAPI** — FastAPI resolve type hint runtime để wire DI; stringized
  annotations làm `Request` bị treat như query param.
- **Step budget mặc định 8** — đủ cho hầu hết RAG + 1-2 tool
  follow-up. Tăng khi agent cần khám phá nhiều bước (deep research).
- **JSON action protocol** đôi khi LLM trả markdown fence — runtime
  có salvage logic nhưng prompt ngắn gọn vẫn tốt hơn.
- **Tool trả `ToolError`** thì agent loop tự retry; lỗi exception
  khác propagate. Phân biệt rõ: expected vs unexpected.
- **`current_user` ContextVar** không tự propagate qua ThreadPool —
  mẫu Parallel / Voting tự xử lý; custom worker pool cần
  `copy_context()` thủ công.

## Đọc thêm

- [Building Effective Agents — Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- `examples/recipes_demo.py` — demo chạy được 4 recipe
- `tests/test_agents.py`, `tests/test_agent_recipes.py` — contract tests
