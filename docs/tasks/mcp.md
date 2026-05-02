# MCP — cầu nối với Model Context Protocol

## TL;DR — gợi ý của chúng tôi

Mô-đun `nom.mcp` là cây cầu MCP hai chiều:

- **Máy chủ** mở các công cụ `nom.agents.Tool` cho chương trình
  khách (Claude Desktop, Cursor, Zed, các khung tác tử khác) qua
  JSON-RPC 2.0.
- **Chương trình khách** bọc máy chủ MCP bên ngoài thành công cụ
  cục bộ để `nom.agents` tiêu thụ.

Triển khai thuần — không phụ thuộc gói `mcp` SDK — giúp giữ bề mặt
phụ thuộc nhỏ và toàn quyền kiểm soát chuỗi nhật ký kiểm toán. Mọi
lượt gọi công cụ qua máy chủ đều ghi vào chuỗi ký HMAC của
`nom.compliance`.

## Bức tranh công khai

| SDK / Máy chủ | Giấy phép | Định dạng | Kết luận |
|---|---|---|---|
| `mcp` SDK Python (Anthropic) | MIT | Không liên quan safetensors | Tốt, nhưng kéo theo pydantic-settings + ngăn xếp WebSocket — không dùng làm phụ thuộc mặc định |
| `mcp-server-everything` (TS) | MIT | Không áp dụng | Tham khảo; không dùng làm phụ thuộc |
| `mcp-server-filesystem` (TS) | MIT | Không áp dụng | Tham khảo thiết kế; chúng ta xây thuần `FileGlob` / `JSONField` |

Triển khai thuần gồm 4 file ngắn: `types.py` (vỏ tin nhắn),
`server.py` (bộ phân tải JSON-RPC), `client.py` (lớp gọi không phụ
thuộc loại đường truyền), `integrations/builtin.py` (3 công cụ
khởi đầu không cần khoá truy cập).

## Đường ống của chúng tôi

```
nom.mcp
├── types.py             ── MCPRequest, MCPResponse, MCPTool, MCPToolResult
├── server.py            ── MCPServer.handle_message + serve_stdio
├── client.py            ── MCPClient + MCPRemoteTool + http_transport
└── integrations/        ── công cụ khởi đầu không cần khoá truy cập
    └── builtin.py       ── FileGlobTool, JSONFieldTool, CurrentTimeTool
```

### Máy chủ — mở công cụ cho chương trình khách MCP

```python
from nom.compliance import AuditLog
from nom.mcp import MCPServer
from nom.mcp.integrations import default_catalog

audit = AuditLog.sqlite("audit.db", signing_key=key)
server = MCPServer(
    server_name="nom-vn",
    tools=default_catalog(file_root=Path("./project")),
    audit_log=audit,
)
server.serve_stdio()  # vòng lặp dừng-luồng; Claude Desktop / Cursor
                      # giao tiếp qua đầu vào / đầu ra chuẩn
```

Lệnh tắt:

```bash
nom mcp-serve --include nlp,builtin,integrations --file-root ./project
```

Cấu hình Claude Desktop:

```json
{
  "mcpServers": {
    "nom-vn": {
      "command": "nom",
      "args": ["mcp-serve"]
    }
  }
}
```

### Chương trình khách — gọi máy chủ MCP từ tác tử

```python
from nom.agents import SingleAgent
from nom.mcp import MCPClient
from nom.mcp.client import http_transport, make_remote_tools

client = MCPClient(transport=http_transport("https://mcp.example.vn/rpc"))
tools = make_remote_tools(client)  # khám phá danh sách qua tools/list

agent = SingleAgent(name="hybrid", llm=my_llm, tools=tools)
# Tác tử gọi công cụ ở xa giống hệt công cụ cục bộ — runtime không
# biết khác biệt.
```

## Bộ tích hợp có sẵn

Hàm `nom.mcp.integrations.default_catalog()` đóng gói 3 công cụ
không cần khoá truy cập, an toàn để bật trên cài đặt mới:

| Công cụ | Tham số | Dùng cho |
|---|---|---|
| `file_glob` | `{pattern}` | Liệt kê file khớp mẫu glob trong thư mục được phép (chặn vượt qua thư mục cha) |
| `json_field` | `{path, field}` | Đọc một trường JSON theo đường dẫn dấu chấm; tránh nuốt cả file lớn vào ngữ cảnh mô hình |
| `current_time` | `{}` | Trả về thời điểm hiện tại theo ISO 8601 và số giây Unix; vá lỗi mô hình ngôn ngữ tự bịa ngày |

Triển khai sản xuất bổ sung các bộ tích hợp cần khoá truy cập qua
gói `nom-vn-enterprise`:

| Công cụ doanh nghiệp | Plugin | Dùng cho |
|---|---|---|
| Office (DOCX/XLSX/PPTX/Outlook/Teams) | `nom_ee.connectors.office` | Trả lời từ tài liệu Microsoft 365 |
| GitHub PR / issue | `nom_ee.connectors.github` | Triage PR, tóm tắt thread issue |
| Tìm kiếm SharePoint | `nom_ee.connectors.sharepoint` | Hỏi-đáp trên kho tài liệu nội bộ |

(Đợt phát hành kế tiếp — chưa ra mắt.)

## Kiểm toán và tuân thủ

Tham số `MCPServer(audit_log=…)` ghi mỗi lần `tools/call` vào chuỗi
ký HMAC:

```python
event = audit_log.emit(
    actor="mcp:nom-vn",
    action="mcp.tools.call",
    payload={"tool": "file_glob", "ok": True, "output_len": 1234},
)
```

Người kiểm toán phát lại được toàn bộ lưu lượng MCP cùng với lưu
lượng gọi mô hình ngôn ngữ; chuỗi ký phát hiện được mọi sửa đổi
hậu kỳ. Đây là điểm khác chính so với việc gọi `mcp` SDK trực tiếp:
nhật ký kiểm toán là trục chính, không phải lớp gắn thêm.

## Bẫy thường gặp

- **Đầu ra chuẩn không bộ đệm** — Claude Desktop chờ JSON theo từng
  dòng. Cần `sys.stdout.flush()` sau mỗi phản hồi (máy chủ đã xử
  lý sẵn).
- **Thông báo JSON-RPC không có `id`** → máy chủ trả về `None`,
  không ghi phản hồi — đúng đặc tả.
- **Lỗi công cụ vs lỗi giao thức** — Lỗi công cụ (`isError: true`)
  dành cho thất bại có thể đoán trước (không tìm thấy file, validate
  không qua). Lỗi RPC (`error: {code, message}`) dành cho lỗi giao
  thức (sai tham số, không tìm thấy phương thức).
- **HTTP transport** — điểm cuối phải nhận vỏ JSON-RPC (`POST /rpc`,
  `content-type: application/json`). Không phải mọi máy chủ MCP đều
  mở HTTP — Claude Desktop chỉ dùng đầu vào / đầu ra chuẩn.
- **Validate JSON-Schema** — máy chủ không tự kiểm tra tham số theo
  JSON-Schema lúc chạy (giữ cho phụ thuộc nhỏ); công cụ tự kiểm tra
  trong `call()`. Hướng dẫn của Anthropic cũng đề nghị công cụ tự
  phòng vệ trên đầu vào.

## Đọc thêm

- [Đặc tả MCP của Anthropic](https://modelcontextprotocol.io)
- `examples/recipes_demo.py` — soạn tác tử và phân phối công cụ.
- [Trang tác tử](/tasks/agents) — cách tác tử dùng công cụ MCP.
