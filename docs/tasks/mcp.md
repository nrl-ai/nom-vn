# MCP — Model Context Protocol bridge

## TL;DR — gợi ý của chúng tôi

`nom.mcp` là cầu MCP hai chiều: server expose `nom.agents.Tool` cho
client (Claude Desktop, Cursor, Zed, agent framework khác) qua
JSON-RPC 2.0; client wrap MCP server bên ngoài thành local Tool để
`nom.agents` tiêu thụ. Native impl, không phụ thuộc `mcp` SDK —
giữ dep surface mỏng và audit trace owned end-to-end. Mọi tool call
qua server có thể audit qua chuỗi ký HMAC của `nom.compliance`.

## Bức tranh công khai

| SDK / Server | License | Format | Kết luận |
|---|---|---|---|
| Anthropic `mcp` Python SDK | MIT | safetensors-irrelevant | Tốt, nhưng kéo theo pydantic-settings + WS stack — không dùng default |
| `mcp-server-everything` (TS) | MIT | N/A | Reference; không dùng làm dep |
| `mcp-server-filesystem` (TS) | MIT | N/A | Tham khảo design; ta build native FileGlob/JSON tools |

Native impl là 4 file ngắn: `types.py` (envelope), `server.py`
(JSON-RPC dispatcher), `client.py` (transport-agnostic caller),
`integrations/builtin.py` (3 starter tool credential-free).

## Pipeline của chúng tôi

```
nom.mcp
├── types.py             ── MCPRequest, MCPResponse, MCPTool, MCPToolResult
├── server.py            ── MCPServer.handle_message + serve_stdio
├── client.py            ── MCPClient + MCPRemoteTool + http_transport
└── integrations/        ── built-in credential-free tools
    └── builtin.py       ── FileGlobTool, JSONFieldTool, CurrentTimeTool
```

### Server — expose tools to MCP clients

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
server.serve_stdio()  # blocks; Claude Desktop / Cursor talk over stdin/stdout
```

CLI shortcut:

```bash
nom mcp-serve --include nlp,builtin,integrations --file-root ./project
```

Claude Desktop config:

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

### Client — consume external MCP servers from agents

```python
from nom.agents import SingleAgent
from nom.mcp import MCPClient
from nom.mcp.client import http_transport, make_remote_tools

client = MCPClient(transport=http_transport("https://mcp.example.vn/rpc"))
tools = make_remote_tools(client)  # discover via tools/list

agent = SingleAgent(name="hybrid", llm=my_llm, tools=tools)
# Agent calls remote tools as if they were local — runtime doesn't know.
```

## Built-in integrations

`nom.mcp.integrations.default_catalog()` ship 3 tool không cần
credential, an toàn để bật trên fresh install:

| Tool | Schema | Use case |
|---|---|---|
| `file_glob` | `{pattern}` | Liệt kê file khớp glob trong allow-listed root (path traversal blocked) |
| `json_field` | `{path, field}` | Đọc một field JSON theo dotted path; tránh nuốt cả file lớn vào LLM context |
| `current_time` | `{}` | Trả ISO 8601 UTC + epoch seconds; vá lỗi LLM hallucinate ngày |

Production deployments thêm credentialed integration qua
`nom-vn-enterprise`:

| EE Tool | Plugin | Use case |
|---|---|---|
| Office (DOCX/XLSX/PPTX/Outlook/Teams) | `nom_ee.connectors.office` | Trả lời từ tài liệu Microsoft 365 |
| GitHub PR/issue | `nom_ee.connectors.github` | Triage PR, tóm tắt issue thread |
| SharePoint search | `nom_ee.connectors.sharepoint` | Hỏi-đáp trên kho tài liệu nội bộ |

(Wave kế tiếp — chưa ship.)

## Audit & compliance

`MCPServer(audit_log=…)` ghi mỗi `tools/call` vào chuỗi ký HMAC:

```python
event = audit_log.emit(
    actor="mcp:nom-vn",
    action="mcp.tools.call",
    payload={"tool": "file_glob", "ok": True, "output_len": 1234},
)
```

Inspector replay được toàn bộ traffic MCP cùng lúc với traffic LLM,
chuỗi ký phát hiện sửa đổi sau-thì-thật. Đây là điểm khác chính so
với việc gọi `mcp` SDK trực tiếp — audit là trunk, không phải
decoration.

## Bẫy thường gặp

- **Stdio không buffer** — Claude Desktop expect line-delimited
  JSON. Đảm bảo `sys.stdout.flush()` sau mỗi response (server đã
  xử lý sẵn).
- **JSON-RPC notification (no `id`)** → server return None, không
  ghi response — đúng spec.
- **Tool error vs RPC error** — Tool error (`isError: true`) cho
  predictable failure (file not found, validation reject). RPC
  error (`error: {code, message}`) cho protocol error (invalid
  params, method not found).
- **HTTP transport** — endpoint phải accept JSON-RPC envelope
  (`POST /rpc`, content-type `application/json`). Không phải mọi
  MCP server expose HTTP — Claude Desktop chỉ dùng stdio.
- **Schema validation** — server không validate args bằng JSON-Schema
  runtime (giữ dep nhỏ); tool tự validate trong `call()`. Anthropic
  guide khuyến nghị tool tự defensive trên args.

## Đo và benchmark

14 test cho `nom.mcp` core (server + client + round-trip với
SingleAgent), 19 test cho `nom.mcp.integrations` (FileGlob, JSONField,
CurrentTime). Tổng 33 test.

## Đọc thêm

- [Anthropic MCP spec](https://modelcontextprotocol.io)
- `examples/recipes_demo.py` — agent compose + tool dispatch
- `tests/test_mcp.py`, `tests/test_mcp_integrations.py` — contract tests
- `docs/tasks/agents.md` — cách agent consume MCP tool
