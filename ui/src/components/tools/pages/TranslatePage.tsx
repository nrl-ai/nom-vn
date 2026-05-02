import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRightLeft,
  Download,
  FileText,
  Languages,
  Play,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Segmented, Select } from "../options";
import { TextInput } from "../TextInput";
import { CopyButton } from "../CopyButton";
import { useToolRunner } from "../useToolRunner";
import { useTranslateFile, useTranslateText } from "@/api/queries";
import type { TranslateBackend, TranslateLang } from "@/api/types";

const STORAGE_KEY = "nom:tool:translate";

type Mode = "text" | "file";

interface PersistedState {
  mode: Mode;
  text: string;
  source: TranslateLang;
  target: TranslateLang;
  backend: TranslateBackend;
  modelId: string;
}

const DEFAULT_STATE: PersistedState = {
  mode: "text",
  text: "",
  source: "vi",
  target: "en",
  backend: "llm",
  modelId: "",
};

const HF_MODEL_OPTIONS: ReadonlyArray<{
  value: string;
  label: string;
  hint?: string;
}> = [
  {
    value: "google/madlad400-3b-mt",
    label: "MADLAD-400-3B (Apache, 3B specialist)",
    hint: "Tải khoảng 6 GB lần đầu.",
  },
  {
    value: "facebook/m2m100_418M",
    label: "m2m100-418M (MIT, nhỏ chạy CPU được)",
    hint: "418 M tham số, CPU dùng ổn.",
  },
];

function loadPersisted(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    const parsed = JSON.parse(raw) as Partial<PersistedState>;
    return {
      ...DEFAULT_STATE,
      ...parsed,
      mode: parsed.mode === "file" ? "file" : "text",
    };
  } catch {
    return DEFAULT_STATE;
  }
}

export function TranslatePage() {
  const initial = useMemo(loadPersisted, []);
  const [mode, setMode] = useState<Mode>(initial.mode);
  const [text, setText] = useState(initial.text);
  const [source, setSource] = useState<TranslateLang>(initial.source);
  const [target, setTarget] = useState<TranslateLang>(initial.target);
  const [backend, setBackend] = useState<TranslateBackend>(initial.backend);
  const [modelId, setModelId] = useState<string>(initial.modelId);
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const translateText = useTranslateText();
  const translateFile = useTranslateFile();

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ mode, text, source, target, backend, modelId } as PersistedState),
      );
    } catch {
      /* ignore quota */
    }
  }, [mode, text, source, target, backend, modelId]);

  // Keep target in lockstep with source when user picks the same lang
  // — single-string translation rejects same-source-target server-side.
  const swapDirection = useCallback(() => {
    setSource(target);
    setTarget(source);
  }, [source, target]);

  const onRunText = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || translateText.isPending || source === target) return;
    translateText.mutate({
      text: trimmed,
      source,
      target,
      backend,
      modelId: backend === "hf" ? modelId || undefined : undefined,
    });
  }, [text, source, target, backend, modelId, translateText]);

  const onRunFile = useCallback(() => {
    if (!file || translateFile.isPending || source === target) return;
    translateFile.mutate(
      {
        file,
        source,
        target,
        backend,
        modelId: backend === "hf" ? modelId || undefined : undefined,
      },
      {
        onSuccess: ({ blob, filename, stats }) => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
          toast.success(
            `Đã dịch ${stats.paragraphs_translated} đoạn` +
              (stats.paragraphs_failed > 0 ? `, ${stats.paragraphs_failed} lỗi` : ""),
          );
        },
      },
    );
  }, [file, source, target, backend, modelId, translateFile]);

  const isTextMode = mode === "text";
  const onRun = isTextMode ? onRunText : onRunFile;
  const canRun =
    source !== target &&
    (isTextMode ? !!text.trim() && !translateText.isPending : !!file && !translateFile.isPending);

  useToolRunner(onRun, canRun);

  const errMsg = isTextMode
    ? translateText.error
      ? (translateText.error as Error).message
      : null
    : translateFile.error
      ? (translateFile.error as Error).message
      : null;

  useEffect(() => {
    if (errMsg) toast.error(`Dịch thất bại: ${errMsg}`);
  }, [errMsg]);

  const result = translateText.data;
  const fileResult = translateFile.data;
  const pending = translateText.isPending || translateFile.isPending;

  const sameLangWarning = source === target ? "Ngôn ngữ nguồn và đích phải khác nhau." : null;

  return (
    <ToolShell
      icon={Languages}
      title="Dịch thuật"
      subtitle="Việt ↔ Anh, giữ nguyên định dạng"
      pending={pending}
      options={
        <>
          <OptionRow label="Chế độ">
            <Segmented<Mode>
              value={mode}
              onChange={setMode}
              options={[
                { value: "text", label: "Văn bản" },
                { value: "file", label: "File .docx" },
              ]}
            />
          </OptionRow>

          <OptionRow label="Hướng dịch" hint="Bấm mũi tên để đổi chiều.">
            <div className="flex items-center gap-1.5">
              <Select<TranslateLang>
                value={source}
                onChange={setSource}
                options={[
                  { value: "vi", label: "Tiếng Việt" },
                  { value: "en", label: "English" },
                ]}
              />
              <button
                type="button"
                onClick={swapDirection}
                className="border border-ink bg-paper px-2 py-1.5 text-ink hover:bg-bg-soft"
                aria-label="Đổi chiều dịch"
                title="Đổi chiều dịch"
              >
                <ArrowRightLeft size={14} />
              </button>
              <Select<TranslateLang>
                value={target}
                onChange={setTarget}
                options={[
                  { value: "vi", label: "Tiếng Việt" },
                  { value: "en", label: "English" },
                ]}
              />
            </div>
          </OptionRow>

          <OptionRow
            label="Backend"
            hint={
              backend === "llm"
                ? "Dùng LLM trò chuyện đã có sẵn — không tải thêm."
                : "Mô hình dịch chuyên dụng — lần đầu tải vài GB."
            }
          >
            <Segmented<TranslateBackend>
              value={backend}
              onChange={setBackend}
              options={[
                { value: "llm", label: "LLM" },
                { value: "hf", label: "HF specialist" },
              ]}
            />
          </OptionRow>

          {backend === "hf" && (
            <OptionRow label="Mô hình HF">
              <Select<string>
                value={modelId || HF_MODEL_OPTIONS[0].value}
                onChange={setModelId}
                options={HF_MODEL_OPTIONS}
              />
              <p className="mt-1 text-[11.5px] leading-snug text-ink-soft">
                {HF_MODEL_OPTIONS.find((m) => m.value === (modelId || HF_MODEL_OPTIONS[0].value))
                  ?.hint ?? ""}
              </p>
            </OptionRow>
          )}

          <OptionRow label="API">
            <code className="block bg-bg-soft px-2 py-1 font-mono text-[11px]">
              {isTextMode ? "POST /api/tools/translate" : "POST /api/tools/translate/file"}
            </code>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-ink-mute">
            {isTextMode
              ? result
                ? `${result.translation.length} ký tự đầu ra`
                : "Bấm ⌘/Ctrl + Enter để chạy"
              : fileResult
                ? `${fileResult.stats.paragraphs_translated} đoạn dịch · ${fileResult.stats.chars_in.toLocaleString()} → ${fileResult.stats.chars_out.toLocaleString()} ký tự`
                : "Chọn file .docx, sau đó bấm Chạy"}
          </span>
          <Button variant="accent" size="md" onClick={onRun} disabled={!canRun}>
            {pending ? <Spinner /> : <Play size={14} />}
            Chạy
          </Button>
        </div>
      }
    >
      {sameLangWarning && (
        <div className="flex items-start gap-2 border border-accent bg-paper px-3 py-2 text-sm text-accent">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{sameLangWarning}</span>
        </div>
      )}

      {isTextMode ? (
        <>
          <TextInput
            value={text}
            onChange={setText}
            rows={6}
            placeholder={
              source === "vi" ? "Nhập văn bản tiếng Việt …" : "Enter English text to translate …"
            }
          />

          {errMsg && (
            <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>{errMsg}</span>
            </div>
          )}

          {result ? (
            <Panel
              label="bản dịch"
              hint={result.backend === "hf" ? `mô hình: ${result.model_id ?? "?"}` : "qua LLM"}
              rightSlot={<CopyButton text={result.translation} label="bản dịch" />}
            >
              <pre className="vn-text whitespace-pre-wrap break-words font-mono text-sm text-ink">
                {result.translation}
              </pre>
            </Panel>
          ) : (
            !errMsg && (
              <EmptyHint>
                Bấm <span className="mx-1 font-mono text-ink">Chạy</span>
                (hoặc <span className="font-mono text-ink">⌘/Ctrl + Enter</span>) để dịch.
              </EmptyHint>
            )
          )}
        </>
      ) : (
        <>
          <div className="border border-line bg-paper p-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setFile(f);
              }}
            />
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm text-ink">
                  <FileText size={14} className="shrink-0 text-accent" />
                  <span className="truncate font-mono">
                    {file ? file.name : "Chưa chọn file .docx"}
                  </span>
                </div>
                {file && (
                  <p className="mt-1 font-mono text-[11px] text-ink-mute">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                <Upload size={13} />
                Chọn .docx
              </Button>
            </div>
            <p className="mt-3 text-[11.5px] leading-snug text-ink-soft">
              v0.1 chỉ hỗ trợ <code className="font-mono">.docx</code>. Định dạng (heading, bullet,
              bảng, header / footer) được giữ nguyên; định dạng phụ trong cùng đoạn (ví dụ một từ in
              đậm giữa câu) có thể bị mất.
            </p>
          </div>

          {errMsg && (
            <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>{errMsg}</span>
            </div>
          )}

          {fileResult ? (
            <Panel
              label="kết quả"
              hint={`${fileResult.stats.paragraphs_translated} đoạn · ${fileResult.stats.paragraphs_skipped} bỏ qua · ${fileResult.stats.paragraphs_failed} lỗi`}
              rightSlot={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const url = URL.createObjectURL(fileResult.blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = fileResult.filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                  }}
                >
                  <Download size={13} />
                  Tải lại
                </Button>
              }
            >
              <p className="text-sm text-ink">
                File <span className="font-mono">{fileResult.filename}</span> đã được tải xuống.
              </p>
              <ul className="mt-2 space-y-1 font-mono text-[11.5px] text-ink-soft">
                <li>
                  Backend: <span className="text-ink">{fileResult.stats.backend}</span>
                  {fileResult.stats.model_id ? ` · ${fileResult.stats.model_id}` : ""}
                </li>
                <li>
                  Ký tự:{" "}
                  <span className="text-ink">{fileResult.stats.chars_in.toLocaleString()}</span> →{" "}
                  <span className="text-ink">{fileResult.stats.chars_out.toLocaleString()}</span>
                </li>
              </ul>
            </Panel>
          ) : (
            !errMsg && (
              <EmptyHint>
                Chọn một file <span className="mx-1 font-mono text-ink">.docx</span> rồi bấm Chạy.
                File dịch sẽ tự động tải về.
              </EmptyHint>
            )
          )}
        </>
      )}
    </ToolShell>
  );
}
