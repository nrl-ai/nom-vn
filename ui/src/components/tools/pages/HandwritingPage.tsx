import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileSearch, PenLine, Play, Upload } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CopyButton } from "../CopyButton";
import { ToolShell, Panel, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow } from "../options";
import { useToolRunner } from "../useToolRunner";
import { useOcrHandwriting } from "@/api/queries";

const SUPPORTED_EXTS = [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"];
const ACCEPT_ATTR = SUPPORTED_EXTS.join(",");

function isSupported(filename: string): boolean {
  const dot = filename.lastIndexOf(".");
  if (dot < 0) return false;
  return SUPPORTED_EXTS.includes(filename.slice(dot).toLowerCase());
}

export function HandwritingPage() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const ocr = useOcrHandwriting();

  // Build / tear down the object-URL preview alongside the file. Without
  // the cleanup an old URL leaks each time the user picks a new image.
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const onRun = useCallback(() => {
    if (!file || ocr.isPending) return;
    if (!isSupported(file.name)) {
      toast.error(`Định dạng không hỗ trợ: ${file.name}`);
      return;
    }
    ocr.mutate(
      { file },
      {
        onError: (err) => toast.error(`OCR thất bại: ${(err as Error).message}`),
      },
    );
  }, [file, ocr]);

  const canRun = !!file && !ocr.isPending && isSupported(file.name);
  useToolRunner(onRun, canRun);

  const result = ocr.data;
  const errMsg = ocr.error ? (ocr.error as Error).message : null;

  return (
    <ToolShell
      icon={PenLine}
      title="OCR chữ viết tay"
      subtitle="Vintern-1B-v3_5 · biểu mẫu / ghi chú / CMND"
      pending={ocr.isPending}
      options={
        <>
          <OptionRow label="Mô hình">
            <code className="block bg-bg-soft px-2 py-1 font-mono text-[11px] text-ink">
              5CD-AI/Vintern-1B-v3_5
            </code>
            <p className="meta mt-1.5 normal-case tracking-normal">
              MIT · safetensors · 0.9 B · ~4-6 GB VRAM
            </p>
          </OptionRow>

          <OptionRow label="Định dạng được hỗ trợ">
            <p className="meta normal-case tracking-normal">{SUPPORTED_EXTS.join(" · ")}</p>
          </OptionRow>

          <OptionRow label="Lưu ý quan trọng">
            <p className="text-[11.5px] leading-snug text-ink-soft">
              Truyền cả trang, không cắt từng dòng. VLM ảo trên line crops &lt; 60 px chiều ngắn —
              cạm bẫy đã đo trên qwen2.5vl 33 % CER với chữ in clean.
            </p>
          </OptionRow>

          <OptionRow label="Khảo cứu">
            <a
              className="inline-flex items-center gap-1 text-[12px] text-accent underline hover:text-ink"
              href="https://github.com/nrl-ai/nom-vn/blob/main/docs/research/2026-05-03-vn-handwriting-ocr-survey.md"
              target="_blank"
              rel="noreferrer"
            >
              <FileSearch size={12} />
              So sánh ứng viên
            </a>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="meta">
            {result
              ? `${result.n_chars} ký tự đã trích · ${result.model}`
              : !file
                ? "Chọn ảnh để bắt đầu"
                : "Sẵn sàng — bấm OCR để chạy"}
          </span>
          <Button variant="primary" size="md" onClick={onRun} disabled={!canRun}>
            {ocr.isPending ? <Spinner /> : <Play size={14} />}
            OCR
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
          if (dropped && isSupported(dropped.name)) setFile(dropped);
          else if (dropped) toast.error(`Định dạng không hỗ trợ: ${dropped.name}`);
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
                <PenLine size={16} className="shrink-0 text-accent" />
              )}
              <span className="truncate font-mono">
                {file ? file.name : "Chưa chọn ảnh chữ tay"}
              </span>
            </div>
            {file && (
              <p className="meta mt-1 normal-case tracking-normal">
                {(file.size / 1024).toFixed(1)} KB · sẵn sàng OCR
              </p>
            )}
            {!file && (
              <p className="mt-1 text-[11.5px] leading-snug text-ink-soft">
                Kéo thả vào đây, hoặc bấm nút bên phải. Hỗ trợ {SUPPORTED_EXTS.join(" · ")}.
              </p>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
            <Upload size={13} />
            {file ? "Đổi ảnh" : "Chọn ảnh"}
          </Button>
        </div>

        {previewUrl && (
          <div className="mt-3 max-h-[280px] overflow-hidden border border-line bg-bg-soft">
            <img src={previewUrl} alt="preview" className="mx-auto max-h-[280px] object-contain" />
          </div>
        )}
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
          hint={`${result.n_chars} ký tự`}
          rightSlot={<CopyButton text={result.text} label="Sao chép" />}
        >
          <pre className="whitespace-pre-wrap break-words border-l-2 border-accent bg-paper px-3 py-2 font-sans text-sm text-ink">
            {result.text || "(không có chữ trong ảnh)"}
          </pre>
        </Panel>
      ) : (
        !errMsg && (
          <EmptyHint>
            Chọn ảnh PNG/JPG/TIFF/BMP/WebP, sau đó bấm <strong>OCR</strong> (Cmd/Ctrl+Enter). Lần
            đầu chạy có thể mất 30-60 giây để tải mô hình.
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}
