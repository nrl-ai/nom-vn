import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileSearch, Mic, Play, Upload } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CopyButton } from "../CopyButton";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select } from "../options";
import { useToolRunner } from "../useToolRunner";
import { useSttTranscribe } from "@/api/queries";
import type { SttBackend } from "@/api/types";

const STORAGE_KEY = "nom:tool:stt";

interface Persisted {
  backend: SttBackend;
  returnTimestamps: boolean;
}

const DEFAULTS: Persisted = { backend: "phowhisper", returnTimestamps: false };

const BACKEND_OPTIONS: ReadonlyArray<{ value: SttBackend; label: string }> = [
  { value: "phowhisper", label: "PhoWhisper-large — VN-tuned (mặc định)" },
  { value: "whisper-v3", label: "Whisper-large-v3 — code-switch VN↔EN" },
];

const SUPPORTED_EXTS = [".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus", ".webm"];
const ACCEPT_ATTR = "audio/*";

function isSupported(filename: string): boolean {
  const dot = filename.lastIndexOf(".");
  if (dot < 0) return true; // browsers sometimes drop ext on MIME upload — let backend decide
  return SUPPORTED_EXTS.includes(filename.slice(dot).toLowerCase());
}

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Persisted>) };
  } catch {
    return DEFAULTS;
  }
}

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(1);
  return `${m}:${sec.padStart(4, "0")}`;
}

export function SttPage() {
  const initial = useMemo(load, []);
  const [file, setFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [backend, setBackend] = useState<SttBackend>(initial.backend);
  const [returnTimestamps, setReturnTimestamps] = useState(initial.returnTimestamps);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stt = useSttTranscribe();

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ backend, returnTimestamps }));
    } catch {
      /* localStorage may be unavailable */
    }
  }, [backend, returnTimestamps]);

  useEffect(() => {
    if (!file) {
      setAudioUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setAudioUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const onRun = useCallback(() => {
    if (!file || stt.isPending) return;
    if (!isSupported(file.name)) {
      toast.error(`Định dạng không hỗ trợ: ${file.name}`);
      return;
    }
    stt.mutate(
      { file, backend, returnTimestamps },
      {
        onError: (err) => toast.error(`Nhận diện thất bại: ${(err as Error).message}`),
      },
    );
  }, [file, backend, returnTimestamps, stt]);

  const canRun = !!file && !stt.isPending;
  useToolRunner(onRun, canRun);

  const result = stt.data;
  const errMsg = stt.error ? (stt.error as Error).message : null;

  return (
    <ToolShell
      icon={Mic}
      title="Giọng nói → văn bản"
      subtitle="PhoWhisper · Whisper-v3 · giọng Bắc / Trung / Nam"
      pending={stt.isPending}
      options={
        <>
          <OptionRow label="Backend">
            <Select<SttBackend> value={backend} onChange={setBackend} options={BACKEND_OPTIONS} />
            <p className="meta mt-1.5 normal-case tracking-normal">
              {backend === "phowhisper"
                ? "VinAI/PhoWhisper-large · BSD-3 · 1.5 B · 844 h VN training"
                : "openai/whisper-large-v3 · MIT · 1.5 B · multilingual zero-shot"}
            </p>
          </OptionRow>

          <OptionRow label="Tùy chọn">
            <label className="flex cursor-pointer items-center gap-2 text-[12px] text-ink-soft">
              <input
                type="checkbox"
                checked={returnTimestamps}
                onChange={(e) => setReturnTimestamps(e.target.checked)}
                className="h-4 w-4 cursor-pointer accent-accent"
              />
              Trả về timestamps theo đoạn
            </label>
          </OptionRow>

          <OptionRow label="Định dạng được hỗ trợ">
            <p className="meta normal-case tracking-normal">{SUPPORTED_EXTS.join(" · ")}</p>
          </OptionRow>

          <OptionRow label="Khảo cứu">
            <a
              className="inline-flex items-center gap-1 text-[12px] text-accent underline hover:text-ink"
              href="https://github.com/nrl-ai/nom-vn/blob/main/docs/research/2026-05-03-vn-stt-diarization-survey.md"
              target="_blank"
              rel="noreferrer"
            >
              <FileSearch size={12} />
              So sánh STT + diarization
            </a>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="meta">
            {result
              ? `${result.n_chars} ký tự · ${result.model}`
              : !file
                ? "Chọn ghi âm để bắt đầu"
                : "Sẵn sàng — bấm Nhận diện để chạy"}
          </span>
          <Button variant="primary" size="md" onClick={onRun} disabled={!canRun}>
            {stt.isPending ? <Spinner /> : <Play size={14} />}
            Nhận diện
          </Button>
        </div>
      }
    >
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
          if (dropped) setFile(dropped);
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_ATTR}
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm text-ink">
              {file ? (
                <CheckCircle2 size={16} className="shrink-0 text-accent" />
              ) : (
                <Mic size={16} className="shrink-0 text-accent" />
              )}
              <span className="truncate font-mono">{file ? file.name : "Chưa chọn ghi âm"}</span>
            </div>
            {file && (
              <p className="meta mt-1 normal-case tracking-normal">
                {(file.size / 1024 / 1024).toFixed(2)} MB · sẵn sàng
              </p>
            )}
            {!file && (
              <p className="mt-1 text-[11.5px] leading-snug text-ink-soft">
                Kéo thả file âm thanh, hoặc bấm nút bên phải. Hỗ trợ {SUPPORTED_EXTS.join(" · ")}.
              </p>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
            <Upload size={13} />
            {file ? "Đổi" : "Chọn file"}
          </Button>
        </div>

        {audioUrl && <audio src={audioUrl} controls className="mt-3 w-full" preload="metadata" />}
      </div>

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {result ? (
        <Panel
          label="Kết quả"
          hint={`${result.model}${result.language ? ` · ${result.language}` : ""}`}
          rightSlot={<CopyButton text={result.text} label="Sao chép" />}
        >
          <pre className="whitespace-pre-wrap break-words border-l-2 border-accent bg-paper px-3 py-2 font-sans text-sm text-ink">
            {result.text || "(không nhận diện được giọng nói)"}
          </pre>
          {result.segments && result.segments.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-[12px] text-ink-soft hover:text-ink">
                {result.segments.length} đoạn timestamp
              </summary>
              <ol className="mt-2 space-y-1">
                {result.segments.map((s, i) => (
                  <li
                    key={i}
                    className="flex gap-2 border-l-2 border-line bg-paper px-3 py-1.5 text-[13px]"
                  >
                    <span className="meta-strong shrink-0 text-accent">
                      {fmtTime(s.start)}–{fmtTime(s.end)}
                    </span>
                    <span className="vn-text text-ink">{s.text}</span>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </Panel>
      ) : (
        !errMsg && (
          <EmptyHint>
            Chọn file âm thanh, sau đó bấm <strong>Nhận diện</strong> (Cmd/Ctrl+Enter). Lần đầu có
            thể mất 30-60 giây để tải mô hình. Audio dài tự chunk 30 giây.
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}
