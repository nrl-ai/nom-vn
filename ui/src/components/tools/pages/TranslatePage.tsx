import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  FileText,
  Languages,
  Play,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Segmented, Select } from "../options";
import { TextInput } from "../TextInput";
import { CopyButton } from "../CopyButton";
import { useToolRunner } from "../useToolRunner";
import { useBgJob, useStartTranslateJob, useTranslateText } from "@/api/queries";
import { JobCard } from "../JobCard";
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
    label: "MADLAD-400-3B — khuyến nghị (chuyên dụng, Apache 2.0)",
    hint: "Đo trên OPUS-100 EN→VN: chrF 40.92, BLEU 23.39, 260 ms/câu (RTX 3090). Lần đầu tải khoảng 6 GB.",
  },
  {
    value: "facebook/m2m100_418M",
    label: "m2m100-418M (nhỏ, MIT, CPU được)",
    hint: "Đo EN→VN: chrF 35.73, BLEU 16.33, 870 ms/câu. Lần đầu tải khoảng 2 GB.",
  },
];

interface DirectionSample {
  label: string;
  text: string;
}

const VN_TO_EN_SAMPLES: DirectionSample[] = [
  {
    label: "Hợp đồng",
    text: "Hợp đồng số 02/HĐ/2025 được lập tại Hà Nội ngày 14 tháng 3 năm 2025 giữa hai bên A và B với tổng giá trị 1.500.000.000 đồng.",
  },
  {
    label: "Hội thoại",
    text: "Bạn có khỏe không? Hôm nay trời đẹp lắm, chúng ta đi ăn phở nhé!",
  },
  {
    label: "Báo chí",
    text: "Theo công bố của Tổng cục Thống kê, GDP quý I năm 2025 tăng 5,66% so với cùng kỳ năm trước, cao hơn dự báo của các tổ chức quốc tế.",
  },
];

const EN_TO_VN_SAMPLES: DirectionSample[] = [
  {
    label: "Contract",
    text: "This Service Agreement is entered into between Party A and Party B as of March 14, 2025, with a total value of 1,500,000,000 VND payable in three instalments.",
  },
  {
    label: "Casual",
    text: "How are you doing today? The weather is lovely — want to grab some pho for lunch?",
  },
  {
    label: "Tin tức",
    text: "According to the General Statistics Office, GDP grew 5.66% in Q1 2025 versus the same period last year, exceeding most international forecasts.",
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
  const startTranslateJob = useStartTranslateJob();
  const [jobId, setJobId] = useState<string | null>(null);
  const jobQ = useBgJob(jobId);

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

  const swapDirection = useCallback(() => {
    setSource(target);
    setTarget(source);
    if (translateText.data) translateText.reset();
  }, [source, target, translateText]);

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
    if (!file || startTranslateJob.isPending || source === target) return;
    startTranslateJob.mutate(
      {
        file,
        source,
        target,
        backend,
        modelId: backend === "hf" ? modelId || undefined : undefined,
      },
      {
        onSuccess: (job) => {
          setJobId(job.id);
          toast.success(`Đã thêm vào hàng đợi: ${file.name}`);
        },
      },
    );
  }, [file, source, target, backend, modelId, startTranslateJob]);

  const isTextMode = mode === "text";
  const onRun = isTextMode ? onRunText : onRunFile;
  const canRun =
    source !== target &&
    (isTextMode
      ? !!text.trim() && !translateText.isPending
      : !!file && !startTranslateJob.isPending);

  useToolRunner(onRun, canRun);

  const errMsg = isTextMode
    ? translateText.error
      ? (translateText.error as Error).message
      : null
    : startTranslateJob.error
      ? (startTranslateJob.error as Error).message
      : null;

  useEffect(() => {
    if (errMsg) toast.error(`Dịch thất bại: ${errMsg}`);
  }, [errMsg]);

  const result = translateText.data;
  const fileJob = jobQ.data;
  const pending = translateText.isPending || startTranslateJob.isPending;

  const sameLangWarning = source === target ? "Ngôn ngữ nguồn và đích phải khác nhau." : null;

  // Sample sentences are only curated for vi↔en. For other languages
  // we hide the sample row to avoid confusing users with VN/EN snippets.
  const samples =
    source === "vi" && target === "en"
      ? VN_TO_EN_SAMPLES
      : source === "en" && target === "vi"
        ? EN_TO_VN_SAMPLES
        : [];

  return (
    <ToolShell
      icon={Languages}
      title="Dịch thuật"
      subtitle="Việt · Anh · 中 · 한 · 日 — giữ nguyên định dạng tệp"
      pending={pending}
      options={
        <>
          <OptionRow label="Chế độ">
            <Segmented<Mode>
              value={mode}
              onChange={setMode}
              options={[
                { value: "text", label: "Văn bản" },
                { value: "file", label: "Tệp" },
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
                  { value: "zh", label: "中文 (Chinese)" },
                  { value: "ko", label: "한국어 (Korean)" },
                  { value: "ja", label: "日本語 (Japanese)" },
                ]}
              />
              <button
                type="button"
                onClick={swapDirection}
                className="border border-ink bg-paper px-2 py-1.5 text-ink hover:bg-accent hover:text-accent-ink"
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
                  { value: "zh", label: "中文 (Chinese)" },
                  { value: "ko", label: "한국어 (Korean)" },
                  { value: "ja", label: "日本語 (Japanese)" },
                ]}
              />
            </div>
          </OptionRow>

          <OptionRow
            label="Cách dịch"
            hint={
              backend === "llm"
                ? "Dùng LLM trò chuyện sẵn có — không tải thêm."
                : "Mô hình dịch chuyên dụng — lần đầu tải vài GB."
            }
          >
            <Segmented<TranslateBackend>
              value={backend}
              onChange={setBackend}
              options={[
                { value: "llm", label: "LLM" },
                { value: "hf", label: "Chuyên dụng" },
              ]}
            />
          </OptionRow>

          {backend === "hf" && (
            <OptionRow label="Mô hình">
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
                : !text.trim()
                  ? "Nhập hoặc dán văn bản, sau đó bấm Dịch"
                  : "Bấm ⌘/Ctrl + Enter để dịch"
              : fileJob
                ? `${fileJob.status} · ${Math.round(fileJob.progress * 100)}%`
                : !file
                  ? "Chọn tệp .docx / .xlsx / .pptx / .txt, sau đó bấm Dịch"
                  : "Sẵn sàng — bấm Dịch để xếp hàng đợi"}
          </span>
          <Button variant="primary" size="md" onClick={onRun} disabled={!canRun}>
            {pending ? <Spinner /> : <Play size={14} />}
            Dịch
          </Button>
        </div>
      }
    >
      {sameLangWarning && (
        <div className="flex items-start gap-2 border-l-2 border-accent bg-paper px-3 py-2 text-sm text-ink">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-accent" />
          <span>{sameLangWarning}</span>
        </div>
      )}

      {isTextMode ? (
        <>
          {samples.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[11px] uppercase tracking-widest text-ink-mute">
                Ví dụ
              </span>
              {samples.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  onClick={() => setText(s.text)}
                  className="border border-line bg-paper px-2 py-1 font-mono text-[11px] text-ink-soft hover:border-accent hover:text-accent"
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}

          <TextInput
            value={text}
            onChange={setText}
            rows={6}
            placeholder={
              source === "vi"
                ? "Nhập hoặc dán văn bản tiếng Việt cần dịch …"
                : "Paste English text to translate into Vietnamese …"
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
              label="Bản dịch"
              hint={result.backend === "hf" ? `mô hình: ${result.model_id ?? "?"}` : "qua LLM"}
              rightSlot={<CopyButton text={result.translation} label="bản dịch" />}
            >
              <pre className="vn-text whitespace-pre-wrap break-words border-l-2 border-accent bg-paper px-3 py-2 font-mono text-sm text-ink">
                {result.translation}
              </pre>
            </Panel>
          ) : (
            !errMsg && (
              <EmptyHint>
                Bấm <span className="mx-1 font-mono text-ink">Dịch</span>
                (hoặc <span className="font-mono text-ink">⌘/Ctrl + Enter</span>) để chạy.
              </EmptyHint>
            )
          )}
        </>
      ) : (
        <>
          <div
            className={cn(
              "border-2 bg-paper p-5 transition-colors",
              file ? "border-ink" : "border-dashed border-accent",
            )}
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              const dropped = e.dataTransfer.files?.[0];
              if (dropped && dropped.name.toLowerCase().endsWith(".docx")) {
                setFile(dropped);
              } else if (dropped) {
                toast.error("Chỉ chấp nhận tệp .docx");
              }
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".docx,.xlsx,.pptx,.txt,.md,.markdown,.rst,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.presentationml.presentation,text/plain,text/markdown"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setFile(f);
              }}
            />
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm text-ink">
                  {file ? (
                    <CheckCircle2 size={16} className="shrink-0 text-accent" />
                  ) : (
                    <FileText size={16} className="shrink-0 text-accent" />
                  )}
                  <span className="truncate font-mono">{file ? file.name : "Chưa chọn tệp"}</span>
                </div>
                {file && (
                  <p className="mt-1 font-mono text-[11px] text-ink-mute">
                    {(file.size / 1024).toFixed(1)} KB · sẵn sàng dịch
                  </p>
                )}
                {!file && (
                  <p className="mt-1 text-[11.5px] leading-snug text-ink-soft">
                    Kéo thả tệp vào đây, hoặc bấm nút bên phải.
                  </p>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                <Upload size={13} />
                {file ? "Đổi tệp" : "Chọn tệp"}
              </Button>
            </div>
          </div>

          <p className="text-[11.5px] leading-snug text-ink-soft">
            Hỗ trợ <code className="font-mono">.docx .xlsx .pptx .txt .md .rst</code>. Cấu trúc
            (heading, danh sách, bảng, header / footer, ô tính, slide) được giữ nguyên; định dạng
            phụ trong cùng đoạn (ví dụ một từ in đậm giữa câu) có thể bị mất — sẽ cải thiện ở phiên
            bản sau.
          </p>

          {errMsg && (
            <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>{errMsg}</span>
            </div>
          )}

          {fileJob ? (
            <div className="space-y-2">
              <h3 className="font-mono text-[11px] uppercase tracking-wide text-ink-soft">
                Tác vụ hiện tại
              </h3>
              <JobCard job={fileJob} />
              <p className="text-[11.5px] leading-snug text-ink-soft">
                Bạn có thể đóng trang này — tác vụ vẫn chạy nền. Mở{" "}
                <a className="font-mono text-accent underline" href="/jobs">
                  Hàng đợi xử lý
                </a>{" "}
                để xem tất cả tác vụ.
              </p>
            </div>
          ) : (
            !errMsg && (
              <EmptyHint>
                Chọn một tệp <span className="mx-1 font-mono text-ink">.docx .xlsx .pptx .txt</span>
                , sau đó bấm Dịch. Tác vụ chạy nền — tiến độ hiển thị ngay tại đây.
              </EmptyHint>
            )
          )}
        </>
      )}
    </ToolShell>
  );
}
