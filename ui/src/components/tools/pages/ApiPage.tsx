import { Code2, ExternalLink, BookOpen, Server, Cpu, Wrench } from "lucide-react";
import { ToolShell, Panel } from "../ToolShell";
import { CopyButton } from "../CopyButton";

interface CurlExampleProps {
  title: string;
  description: string;
  curl: string;
}

function CurlExample({ title, description, curl }: CurlExampleProps) {
  return (
    <Panel
      label={title.toLowerCase()}
      hint={description}
      rightSlot={<CopyButton text={curl} label={title} />}
    >
      <pre className="overflow-x-auto whitespace-pre-wrap break-all border border-line-soft bg-bg-soft p-2 font-mono text-[11.5px] leading-relaxed text-ink">
        {curl}
      </pre>
    </Panel>
  );
}

interface ShellSnippetProps {
  label: string;
  hint?: string;
  command: string;
}

function ShellSnippet({ label, hint, command }: ShellSnippetProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-widest text-ink-mute">
          {label}
        </span>
        <CopyButton text={command} label={label} />
      </div>
      {hint && <p className="text-[11.5px] leading-snug text-ink-soft">{hint}</p>}
      <pre className="overflow-x-auto whitespace-pre-wrap break-all border border-line-soft bg-bg-soft p-2 font-mono text-[11.5px] leading-relaxed text-ink">
        {command}
      </pre>
    </div>
  );
}

export function ApiPage() {
  const base = typeof window !== "undefined" ? window.location.origin : "http://localhost:8080";

  const curlHealth = `curl -s ${base}/api/health`;
  const curlDiacritic = `curl -s -X POST ${base}/api/tools/diacritic/restore \\
  -H 'content-type: application/json' \\
  -d '{"text":"Hop dong nay duoc lap","backend":"rule"}'`;
  const curlStrip = `curl -s -X POST ${base}/api/tools/diacritic/strip \\
  -H 'content-type: application/json' \\
  -d '{"text":"Hợp đồng số 02/HĐ/2025"}'`;
  const curlWord = `curl -s -X POST ${base}/api/tools/tokenize/word \\
  -H 'content-type: application/json' \\
  -d '{"text":"Hợp đồng số 02 được lập","fmt":"list"}'`;
  const curlSent = `curl -s -X POST ${base}/api/tools/tokenize/sentence \\
  -H 'content-type: application/json' \\
  -d '{"text":"Tôi yêu Việt Nam. Bạn có khoẻ không?"}'`;
  const curlNorm = `curl -s -X POST ${base}/api/tools/text/normalize \\
  -H 'content-type: application/json' \\
  -d '{"text":"Tôi yêu Việt Nam"}'`;
  const curlDetect = `curl -s -X POST ${base}/api/tools/text/detect \\
  -H 'content-type: application/json' \\
  -d '{"text":"Hop dong so 02"}'`;
  const curlNoise = `curl -s -X POST ${base}/api/tools/noise/apply \\
  -H 'content-type: application/json' \\
  -d '{"text":"Tôi yêu Việt Nam","preset":"light","seed":42}'`;
  const curlAsk = `curl -s -X POST ${base}/api/spaces/<SPACE_ID>/ask \\
  -H 'content-type: application/json' \\
  -d '{"question":"Hợp đồng có giá bao nhiêu?","top_k":5}'`;

  return (
    <ToolShell
      icon={Code2}
      title="API và cài đặt"
      subtitle="cách chạy và tích hợp máy chủ Nôm"
      options={
        <>
          <div className="mb-3">
            <a
              href="/docs"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 border border-ink bg-paper px-3 py-2 text-sm text-ink transition-colors hover:bg-bg-soft"
            >
              <BookOpen size={14} className="text-accent" />
              <span className="flex-1">OpenAPI / Swagger</span>
              <ExternalLink size={12} className="text-ink-mute" />
            </a>
          </div>
          <div className="mb-3">
            <a
              href="/redoc"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 border border-line bg-paper px-3 py-2 text-sm text-ink transition-colors hover:border-ink hover:bg-bg-soft"
            >
              <BookOpen size={14} className="text-accent" />
              <span className="flex-1">ReDoc</span>
              <ExternalLink size={12} className="text-ink-mute" />
            </a>
          </div>
          <div className="mb-1 mt-4 font-mono text-[11px] uppercase tracking-widest text-ink-mute">
            base url
          </div>
          <pre className="border border-line-soft bg-bg-soft p-2 font-mono text-[11px] text-ink">
            {base}
          </pre>
          <p className="mt-3 text-[11.5px] leading-snug text-ink-soft">
            Tất cả endpoint đều là REST trả về JSON. Mặc định không cần xác thực — web app chạy cục
            bộ cho cá nhân.
          </p>
        </>
      }
    >
      {/* ----------- Setup ----------- */}
      <Panel label="cài đặt và chạy" hint="từ kho mới tới web app chạy trong ~3 phút">
        <div className="space-y-4">
          <ShellSnippet
            label="1. cài nom-vn"
            hint="kéo theo FastAPI, React UI, các parser và embeddings."
            command={'pip install "nom-vn[chat]"'}
          />
          <ShellSnippet
            label="2. khởi động máy chủ"
            hint="lưu trong bộ nhớ — bỏ --in-memory để lưu vào ~/.nom/."
            command={"nom serve --in-memory --port 8080"}
          />
          <ShellSnippet
            label="3. (tuỳ chọn) tạo dữ liệu mẫu"
            hint="tải sẵn vài tài liệu tiếng Việt để bắt đầu hỏi đáp ngay."
            command={"python scripts/seed_demo.py"}
          />
        </div>
      </Panel>

      {/* ----------- LLM backends ----------- */}
      <Panel
        label="llm backend"
        hint="Chat, RAG, và bộ khôi phục dấu LLM cần một LLM. Chọn một trong các con đường sau."
      >
        <div className="space-y-5">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Cpu size={14} className="text-accent" />
              <span className="font-display text-sm font-semibold text-ink">
                Ollama (đơn giản nhất)
              </span>
            </div>
            <div className="space-y-3">
              <ShellSnippet
                label="cài (linux / wsl)"
                command={"curl -fsSL https://ollama.com/install.sh | sh"}
              />
              <ShellSnippet
                label="cài (macos)"
                hint="hoặc tải Ollama.app từ https://ollama.com/download"
                command={"brew install ollama"}
              />
              <ShellSnippet
                label="kéo model mặc định"
                hint="qwen3:8b (~5 GB, khuyến nghị); thay bằng phi4 hoặc qwen3:1.7b nếu máy yếu."
                command={"ollama pull qwen3:8b"}
              />
              <ShellSnippet
                label="chạy ollama (nền)"
                hint="thường tự khởi động sau khi cài; chỉ cần khi `ollama list` không chạy."
                command={"ollama serve &"}
              />
              <ShellSnippet
                label="trỏ Nôm vào một model khác"
                command={"NOM_LLM_MODEL=phi4 nom serve --in-memory"}
              />
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2">
              <Server size={14} className="text-accent" />
              <span className="font-display text-sm font-semibold text-ink">
                llama.cpp (không daemon, tương thích OpenAI)
              </span>
            </div>
            <p className="mb-3 text-[12px] leading-snug text-ink-soft">
              llama.cpp đi kèm <code className="bg-bg-soft px-1">llama-server</code> với endpoint
              tương thích OpenAI <code className="bg-bg-soft px-1">/v1/chat/completions</code>.
              Không cần daemon riêng — Nôm gọi qua adapter <code>nom.llm.LlamaCpp</code>.
            </p>
            <div className="space-y-3">
              <ShellSnippet
                label="cài (mọi hệ điều hành)"
                hint="hoặc tự build: `git clone https://github.com/ggerganov/llama.cpp && make`."
                command={"brew install llama.cpp   # hoặc apt / scoop / cargo"}
              />
              <ShellSnippet
                label="tải GGUF tiếng Việt"
                hint="qwen2.5-7b-instruct-q4_k_m hoặc bất kỳ GGUF nào trên HuggingFace."
                command={
                  "huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF \\\n" +
                  "  qwen2.5-7b-instruct-q4_k_m.gguf --local-dir ./models"
                }
              />
              <ShellSnippet
                label="chạy llama-server"
                hint="--host 127.0.0.1 --port 8081 để khỏi đụng cổng của FastAPI."
                command={
                  "llama-server -m ./models/qwen2.5-7b-instruct-q4_k_m.gguf \\\n" +
                  "  --host 127.0.0.1 --port 8081 --ctx-size 8192"
                }
              />
              <ShellSnippet
                label="trỏ Nôm vào llama-server"
                hint="Adapter `nom.llm.LlamaCpp` không cần API key giả; chỉ cần URL."
                command={
                  "NOM_LLM_BACKEND=llamacpp \\\n" +
                  "NOM_LLAMACPP_URL=http://127.0.0.1:8081/v1 nom serve --in-memory"
                }
              />
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2">
              <Cpu size={14} className="text-accent" />
              <span className="font-display text-sm font-semibold text-ink">
                HuggingFace transformers (in-process)
              </span>
            </div>
            <p className="mb-3 text-[12px] leading-snug text-ink-soft">
              Nạp trực tiếp model HuggingFace bất kỳ vào tiến trình Python, tự tải lên cache lần đầu
              chạy. Không cần daemon nhưng tốn thêm RAM / VRAM.
            </p>
            <ShellSnippet label="cài thêm phần mở rộng" command={'pip install "nom-vn[llm-hf]"'} />
            <ShellSnippet
              label="trỏ Nôm vào một model HF bất kỳ"
              command={
                "NOM_LLM_BACKEND=huggingface \\\n" +
                "NOM_LLM_MODEL=Qwen/Qwen2.5-3B-Instruct nom serve --in-memory"
              }
            />
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2">
              <Wrench size={14} className="text-accent" />
              <span className="font-display text-sm font-semibold text-ink">
                Đám mây (OpenAI / Anthropic)
              </span>
            </div>
            <ShellSnippet
              label="openai"
              hint="đặt OPENAI_API_KEY, không cần Ollama hay llama.cpp."
              command={
                "export OPENAI_API_KEY=sk-...\n" +
                "NOM_LLM_BACKEND=openai NOM_LLM_MODEL=gpt-4o-mini nom serve"
              }
            />
            <ShellSnippet
              label="anthropic"
              command={
                "export ANTHROPIC_API_KEY=sk-ant-...\n" +
                "NOM_LLM_BACKEND=anthropic NOM_LLM_MODEL=claude-haiku-4-5 nom serve"
              }
            />
          </div>
        </div>
      </Panel>

      {/* ----------- Stateless tools ----------- */}
      <Panel label="công cụ stateless — /api/tools/*" hint="không cần không gian, không cần LLM">
        <div className="space-y-3">
          <CurlExample
            title="Health"
            description="kiểm tra phiên bản và năng lực máy chủ"
            curl={curlHealth}
          />
          <CurlExample
            title="Khôi phục dấu (rule)"
            description="tra bảng, không phụ thuộc, ~5 ms"
            curl={curlDiacritic}
          />
          <CurlExample
            title="Bỏ dấu"
            description="chuyển sang ASCII; dùng cho URL slug hoặc khoá tìm kiếm"
            curl={curlStrip}
          />
          <CurlExample title="Tách từ" description="gộp từ ghép theo bảng tra" curl={curlWord} />
          <CurlExample
            title="Tách câu"
            description="tách theo dấu câu tiếng Việt"
            curl={curlSent}
          />
          <CurlExample
            title="Chuẩn hoá"
            description="đưa về NFC và cho biết đầu vào có bị phân rã hay không"
            curl={curlNorm}
          />
          <CurlExample
            title="Nhận diện tiếng Việt"
            description="is_vietnamese và has_diacritics"
            curl={curlDetect}
          />
          <CurlExample
            title="Sinh nhiễu"
            description="(văn bản, kiểu, seed) → văn bản nhiễu, có thể tái hiện"
            curl={curlNoise}
          />
        </div>
      </Panel>

      {/* ----------- RAG ----------- */}
      <Panel
        label="rag / chat — /api/spaces/*"
        hint="cần một không gian và ít nhất một tài liệu đã đánh chỉ mục"
      >
        <CurlExample
          title="Hỏi một câu"
          description="thay <SPACE_ID> bằng ID lấy từ GET /api/spaces"
          curl={curlAsk}
        />
        <p className="mt-3 text-[11.5px] leading-snug text-ink-soft">
          Quy trình đầy đủ: <code className="bg-bg-soft px-1">POST /api/spaces</code> →
          <code className="mx-1 bg-bg-soft px-1">POST /api/spaces/&lt;id&gt;/materials</code>
          (multipart) →
          <code className="mx-1 bg-bg-soft px-1">POST /api/spaces/&lt;id&gt;/index</code>→{" "}
          <code className="bg-bg-soft px-1">POST /api/spaces/&lt;id&gt;/ask</code>. Đầy đủ tham số
          có trong{" "}
          <a className="text-accent underline" href="/docs">
            /docs
          </a>
          .
        </p>
      </Panel>

      <Panel label="python sdk" hint="dùng nom.* trực tiếp, không qua máy chủ">
        <pre className="overflow-x-auto whitespace-pre-wrap break-words border border-line-soft bg-bg-soft p-2 font-mono text-[11.5px] leading-relaxed text-ink">
          {`from nom.text import fix_diacritics, word_tokenize
from nom.text.diacritic_models import HFDiacriticModel
from nom.llm import Ollama

# Diacritic restore — HF default model
restorer = HFDiacriticModel()
print(fix_diacritics("Hop dong nay duoc lap", model=restorer))
# 'Hợp đồng này được lập'

# Word tokenize (zero deps)
print(word_tokenize("Hợp đồng số 02 được lập"))
# ['Hợp đồng', 'số', '02', 'được', 'lập']

# RAG over a folder of docs
from nom.chat.store import MemoryStore
store = MemoryStore(llm=Ollama(model="qwen3:8b"))
sp = store.create_space("Demo")
store.add_material(sp.id, "doc.txt", b"Hợp đồng số HD-001…")
print(store.ask(sp.id, "Số hợp đồng là gì?").text)`}
        </pre>
      </Panel>
    </ToolShell>
  );
}
