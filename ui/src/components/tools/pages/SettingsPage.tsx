import { useEffect, useMemo, useState } from "react";
import {
  Settings,
  Lock,
  Shield,
  Trash2,
  Check,
  AlertTriangle,
  RotateCcw,
  Cpu,
  Cloud,
  HardDrive,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel } from "../ToolShell";
import { OptionRow } from "../options";
import { CopyButton } from "../CopyButton";
import { useHealth, useLlmBackends } from "@/api/queries";
import { getAuthToken, setAuthToken } from "@/api/client";
import { cn } from "@/lib/utils";

const TOP_K_KEY = "nom:chat:top-k";

type BackendId = "ollama" | "llamacpp" | "llamacpp-python" | "huggingface" | "openai" | "anthropic";

const BACKEND_DEFAULTS: Record<BackendId, string> = {
  ollama: "qwen3:8b",
  llamacpp: "llamacpp",
  "llamacpp-python": "hf:bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M",
  huggingface: "Qwen/Qwen2.5-3B-Instruct",
  openai: "gpt-4o-mini",
  anthropic: "claude-haiku-4-5-20251001",
};

function buildLaunchCommand(backend: BackendId, modelId: string): string {
  const env = `NOM_LLM_BACKEND=${backend} NOM_LLM_MODEL='${modelId}'`;
  switch (backend) {
    case "ollama":
      return `${env} nom serve\n# (one-time) ollama pull '${modelId}'`;
    case "llamacpp":
      return (
        `# (one-time) start llama-server externally:\n` +
        `#   llama-server -m <gguf-path> --host 127.0.0.1 --port 8080\n` +
        `${env} NOM_LLAMACPP_URL=http://127.0.0.1:8080/v1 nom serve`
      );
    case "llamacpp-python":
      return (
        `pip install "nom-vn[llamacpp-python]"  # one-time\n` +
        `${env} nom serve  # auto-downloads from HuggingFace on first call`
      );
    case "huggingface":
      return (
        `pip install "nom-vn[llm-hf]"  # one-time\n` +
        `${env} nom serve  # auto-downloads from HuggingFace on first call`
      );
    case "openai":
      return `OPENAI_API_KEY=sk-... ${env} nom serve`;
    case "anthropic":
      return `ANTHROPIC_API_KEY=sk-ant-... ${env} nom serve`;
  }
}

export function SettingsPage() {
  const healthQ = useHealth();
  const backendsQ = useLlmBackends();
  const authRequired = !!healthQ.data?.auth_required;

  const [token, setToken] = useState<string>(() => getAuthToken() ?? "");
  const [tokenSaved, setTokenSaved] = useState(false);

  const activeBackendId = useMemo<BackendId>(() => {
    const cls = backendsQ.data?.active.class ?? "";
    const map: Record<string, BackendId> = {
      Ollama: "ollama",
      LlamaCpp: "llamacpp",
      LlamaCppPython: "llamacpp-python",
      HuggingFace: "huggingface",
      OpenAI: "openai",
      Anthropic: "anthropic",
    };
    return map[cls] ?? "ollama";
  }, [backendsQ.data]);

  const [pickerBackend, setPickerBackend] = useState<BackendId>("ollama");
  const [pickerModel, setPickerModel] = useState<string>("");

  // Sync the picker default when backends load + each time the backend changes.
  useEffect(() => {
    setPickerBackend(activeBackendId);
  }, [activeBackendId]);
  useEffect(() => {
    setPickerModel(BACKEND_DEFAULTS[pickerBackend]);
  }, [pickerBackend]);

  const launchCmd = useMemo(
    () => buildLaunchCommand(pickerBackend, pickerModel || BACKEND_DEFAULTS[pickerBackend]),
    [pickerBackend, pickerModel],
  );

  const [defaultTopK, setDefaultTopK] = useState<number>(() => {
    try {
      const raw = localStorage.getItem(TOP_K_KEY);
      const n = raw ? Number(raw) : 5;
      return Number.isFinite(n) && n >= 1 && n <= 20 ? n : 5;
    } catch {
      return 5;
    }
  });

  const saveToken = () => {
    setAuthToken(token.trim() || null);
    setTokenSaved(true);
    window.setTimeout(() => setTokenSaved(false), 1500);
  };

  const saveTopK = (n: number) => {
    setDefaultTopK(n);
    try {
      localStorage.setItem(TOP_K_KEY, String(n));
    } catch {
      /* noop */
    }
  };

  const resetAll = () => {
    if (!confirm("Reset all per-tool inputs and chat history saved in this browser?")) return;
    try {
      const keys: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith("nom:")) keys.push(k);
      }
      keys.forEach((k) => localStorage.removeItem(k));
    } catch {
      /* noop */
    }
    window.location.reload();
  };

  useEffect(() => {
    // Pull token from storage on mount in case another tab updated it.
    setToken(getAuthToken() ?? "");
  }, []);

  return (
    <ToolShell
      icon={Settings}
      title="Cài đặt"
      subtitle="cài đặt · trạng thái máy chủ · xác thực"
      options={
        <>
          <OptionRow label="Vị trí lưu cài đặt">
            <p className="text-[11.5px] leading-snug text-ink-soft">
              Các tuỳ chọn giao diện được lưu trong{" "}
              <code className="bg-bg-soft px-1">localStorage</code> của trình duyệt. Cấu hình máy
              chủ (LLM, xác thực) bật bằng biến môi trường khi chạy{" "}
              <code className="bg-bg-soft px-1">nom serve</code>.
            </p>
          </OptionRow>
        </>
      }
    >
      {/* Server snapshot */}
      <Panel label="server" hint={healthQ.data ? `v${healthQ.data.version}` : "đang tải…"}>
        {healthQ.data ? (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 font-mono text-[12px]">
            <dt className="text-ink-mute">LLM</dt>
            <dd className="text-ink">
              {healthQ.data.llm}{" "}
              <span className="text-ink-mute">({healthQ.data.llm_class ?? "—"})</span>
            </dd>
            <dt className="text-ink-mute">Embedder</dt>
            <dd className="text-ink">{healthQ.data.embedder}</dd>
            <dt className="text-ink-mute">Lưu trữ</dt>
            <dd className="text-ink">{healthQ.data.store}</dd>
            <dt className="text-ink-mute">OCR (tesseract)</dt>
            <dd>
              {healthQ.data.ocr_available ? (
                <span className="text-ok">có sẵn</span>
              ) : (
                <span className="text-ink-mute">chưa cài đặt</span>
              )}
            </dd>
            <dt className="text-ink-mute">Xác thực</dt>
            <dd>
              {authRequired ? (
                <span className="text-accent-ink">bắt buộc (NOM_AUTH_TOKEN)</span>
              ) : (
                <span className="text-ink-mute">đã tắt (API công khai)</span>
              )}
            </dd>
          </dl>
        ) : (
          <p className="text-sm text-ink-mute">Đang tải…</p>
        )}
      </Panel>

      {/* Auth */}
      <Panel
        label="authentication"
        hint={authRequired ? "Cần token bearer" : "Mở — không yêu cầu token"}
        rightSlot={
          <span
            className={cn(
              "inline-flex items-center gap-1 border px-2 py-0.5 font-mono text-[11px]",
              authRequired
                ? "border-accent bg-accent/10 text-accent-ink"
                : "border-line bg-bg-soft text-ink-mute",
            )}
          >
            {authRequired ? <Lock size={11} /> : <Shield size={11} />}
            {authRequired ? "ON" : "OFF"}
          </span>
        }
      >
        <div className="space-y-3">
          <p className="text-[12px] leading-snug text-ink-soft">
            Bật xác thực ở phía <strong>máy chủ</strong> bằng cách đặt biến môi trường{" "}
            <code className="bg-bg-soft px-1">NOM_AUTH_TOKEN</code> khi chạy:
          </p>
          <pre className="overflow-x-auto whitespace-pre-wrap break-all border border-line-soft bg-bg-soft p-2 font-mono text-[11.5px] leading-relaxed text-ink">
            {"NOM_AUTH_TOKEN=$(openssl rand -hex 24) nom serve --in-memory"}
          </pre>
          <div className="flex justify-end">
            <CopyButton
              text={"NOM_AUTH_TOKEN=$(openssl rand -hex 24) nom serve --in-memory"}
              label="lệnh chạy"
            />
          </div>

          <div className="border-t border-line-soft pt-3">
            <label className="mb-1 block font-mono text-[11px] uppercase tracking-widest text-ink-mute">
              token cho trình duyệt này
            </label>
            <p className="mb-2 text-[11.5px] leading-snug text-ink-soft">
              Khi máy chủ bật xác thực, trình duyệt này sẽ tự thêm{" "}
              <code className="bg-bg-soft px-1">Authorization: Bearer &lt;token&gt;</code> vào mọi
              request đến /api/*. Để trống = không gửi header.
            </p>
            <div className="flex items-center gap-2">
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="dán token vào đây…"
                className="flex-1 border border-ink bg-paper px-2.5 py-1.5 font-mono text-sm text-ink placeholder:text-ink-mute focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
                aria-label="bearer token"
              />
              <Button variant="primary" size="md" onClick={saveToken}>
                {tokenSaved ? <Check size={14} /> : null}
                {tokenSaved ? "Đã lưu" : "Lưu"}
              </Button>
            </div>
            {!authRequired && token && (
              <div className="mt-2 flex items-start gap-2 text-[11.5px] text-ink-mute">
                <AlertTriangle size={12} className="mt-0.5 shrink-0 text-accent" />
                <span>
                  Token đang được lưu nhưng máy chủ hiện <strong>không yêu cầu</strong> xác thực.
                  Đặt <code>NOM_AUTH_TOKEN</code> ở phía máy chủ để kích hoạt.
                </span>
              </div>
            )}
          </div>
        </div>
      </Panel>

      {/* Model + backend */}
      <Panel label="llm backend & model" hint="chọn backend → sao chép lệnh để chạy lại">
        <div className="space-y-4">
          <p className="text-[12px] leading-snug text-ink-soft">
            Backend hiện tại lấy từ <code className="bg-bg-soft px-1">/api/health</code>:{" "}
            <strong>{backendsQ.data?.active.class ?? "—"}</strong>
            {backendsQ.data?.active.model && (
              <>
                {" "}
                · model <code className="bg-bg-soft px-1">{backendsQ.data.active.model}</code>
              </>
            )}
            . Để đổi, đặt biến môi trường <code className="bg-bg-soft px-1">NOM_LLM_BACKEND</code>{" "}
            và <code className="bg-bg-soft px-1">NOM_LLM_MODEL</code> rồi chạy lại (chưa hỗ trợ đổi
            nóng trong cùng tiến trình).
          </p>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {(backendsQ.data?.available ?? []).map((b) => {
              const Icon = b.kind === "cloud" ? Cloud : b.kind === "local-inproc" ? Cpu : HardDrive;
              return (
                <button
                  key={b.id}
                  type="button"
                  onClick={() => setPickerBackend(b.id as BackendId)}
                  disabled={!b.available}
                  className={cn(
                    "flex items-start gap-2 border px-3 py-2 text-left transition-colors",
                    pickerBackend === b.id
                      ? "border-ink bg-paper shadow-editorial-soft"
                      : "border-line bg-paper hover:border-ink",
                    !b.available && "cursor-not-allowed opacity-50",
                  )}
                >
                  <Icon size={14} className="mt-0.5 shrink-0 text-accent" />
                  <span className="min-w-0 flex-1">
                    <span className="vn-text block text-sm font-medium text-ink">{b.label}</span>
                    <span className="block font-mono text-[11px] text-ink-mute">
                      {b.model_hint}
                    </span>
                    {!b.available && (
                      <span className="mt-0.5 block font-mono text-[10.5px] text-danger">
                        cần cài: {b.needs.join(" · ")}
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>

          <div>
            <label className="mb-1 block font-mono text-[11px] uppercase tracking-widest text-ink-mute">
              model id
            </label>
            <input
              type="text"
              value={pickerModel}
              onChange={(e) => setPickerModel(e.target.value)}
              placeholder={BACKEND_DEFAULTS[pickerBackend]}
              className="vn-text block w-full border border-ink bg-paper px-2.5 py-1.5 font-mono text-sm text-ink placeholder:text-ink-mute focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
              aria-label="model id"
            />
            <p className="mt-1 text-[11.5px] leading-snug text-ink-soft">
              {pickerBackend === "huggingface" &&
                "Bất kỳ ID model nào trên HuggingFace — sẽ tự tải về ~/.cache/huggingface."}
              {pickerBackend === "llamacpp-python" &&
                "Đường dẫn tới file GGUF, hoặc 'hf:<repo>:<filename>' để tự tải từ HuggingFace."}
              {pickerBackend === "ollama" &&
                "Model đã có sẵn trong Ollama. Hỗ trợ GGUF từ HuggingFace qua hf.co/<repo>:<tag>."}
              {pickerBackend === "llamacpp" &&
                "Chỉ là nhãn để hiển thị; file GGUF thực sự được chỉ định khi chạy llama-server."}
              {(pickerBackend === "openai" || pickerBackend === "anthropic") &&
                "ID model do nhà cung cấp; cần đặt API key trong biến môi trường."}
            </p>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-widest text-ink-mute">
                lệnh chạy
              </span>
              <CopyButton text={launchCmd} label="lệnh chạy" />
            </div>
            <pre className="overflow-x-auto whitespace-pre-wrap break-all border border-line-soft bg-bg-soft p-2 font-mono text-[11.5px] leading-relaxed text-ink">
              {launchCmd}
            </pre>
          </div>
        </div>
      </Panel>

      {/* UI prefs */}
      <Panel label="ui preferences" hint="lưu trong localStorage">
        <OptionRow
          label="top_k mặc định cho chat"
          hint="Số chunk được truy hồi đưa vào prompt. Mặc định 5."
        >
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={1}
              max={20}
              step={1}
              value={defaultTopK}
              onChange={(e) => saveTopK(Number(e.target.value))}
              className="flex-1 accent-[#b5563a]"
              aria-label="default top_k"
            />
            <span className="w-8 text-right font-mono text-sm text-ink">{defaultTopK}</span>
          </div>
        </OptionRow>
      </Panel>

      {/* Reset */}
      <Panel label="reset" hint="xoá toàn bộ trạng thái lưu trong trình duyệt này">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-md text-[12px] leading-snug text-ink-soft">
            Xoá hết <code className="bg-bg-soft px-1">nom:*</code> trong localStorage (lịch sử chat,
            đầu vào của mỗi tool, backend đã chọn, top_k, token xác thực). Spaces và tài liệu trên
            máy chủ không bị ảnh hưởng.
          </p>
          <div className="flex gap-2">
            <Button variant="danger" size="md" onClick={resetAll}>
              <Trash2 size={14} />
              Đặt lại
            </Button>
            <Button
              variant="ghost"
              size="md"
              onClick={() => window.location.reload()}
              aria-label="Tải lại"
            >
              <RotateCcw size={14} />
              Tải lại
            </Button>
          </div>
        </div>
      </Panel>
    </ToolShell>
  );
}
