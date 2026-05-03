import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileType, Play, Upload } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ToolShell, Spinner, EmptyHint } from "../ToolShell";
import { OptionRow, Select } from "../options";
import { useToolRunner } from "../useToolRunner";
import { JobCard } from "../JobCard";
import { useBgJob, useStartConvertJob } from "@/api/queries";

const STORAGE_KEY = "nom:tool:convert";

interface PersistedState {
  ocrLanguage: string;
}

const DEFAULT_STATE: PersistedState = { ocrLanguage: "vie+eng" };

const SUPPORTED_EXTS = [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"];
const ACCEPT_ATTR = SUPPORTED_EXTS.join(",");

const OCR_LANG_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "vie+eng", label: "Tiếng Việt + tiếng Anh (mặc định)" },
  { value: "vie", label: "Chỉ tiếng Việt" },
  { value: "eng", label: "Chỉ tiếng Anh" },
  { value: "chi_sim+eng", label: "Tiếng Trung giản thể + tiếng Anh" },
  { value: "kor+eng", label: "Tiếng Hàn + tiếng Anh" },
  { value: "jpn+eng", label: "Tiếng Nhật + tiếng Anh" },
];

function loadPersisted(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    return { ...DEFAULT_STATE, ...(JSON.parse(raw) as Partial<PersistedState>) };
  } catch {
    return DEFAULT_STATE;
  }
}

function fileExtIsSupported(name: string): boolean {
  const dot = name.lastIndexOf(".");
  if (dot < 0) return false;
  return SUPPORTED_EXTS.includes(name.slice(dot).toLowerCase());
}

export function ConvertPage() {
  const initial = useMemo(loadPersisted, []);
  const [ocrLanguage, setOcrLanguage] = useState(initial.ocrLanguage);
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const startJob = useStartConvertJob();
  const jobQ = useBgJob(jobId);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ocrLanguage }));
    } catch {
      /* quota */
    }
  }, [ocrLanguage]);

  const onRun = useCallback(() => {
    if (!file || startJob.isPending) return;
    if (!fileExtIsSupported(file.name)) {
      toast.error(`Định dạng không hỗ trợ: ${file.name}`);
      return;
    }
    startJob.mutate(
      { file, ocrLanguage },
      {
        onSuccess: (job) => {
          setJobId(job.id);
          toast.success(`Đã thêm vào hàng đợi: ${file.name}`);
        },
      },
    );
  }, [file, ocrLanguage, startJob]);

  const canRun = !!file && !startJob.isPending && fileExtIsSupported(file.name);
  useToolRunner(onRun, canRun);

  const errMsg = startJob.error ? (startJob.error as Error).message : null;
  useEffect(() => {
    if (errMsg) toast.error(`Chuyển đổi thất bại: ${errMsg}`);
  }, [errMsg]);

  const job = jobQ.data;
  const fileSizeNote = file ? `${(file.size / 1024).toFixed(1)} KB` : null;

  return (
    <ToolShell
      icon={FileType}
      title="Chuyển định dạng"
      subtitle="PDF / ảnh → DOCX có thể chỉnh sửa, OCR cục bộ qua Tesseract"
      pending={startJob.isPending}
      options={
        <>
          <OptionRow label="Ngôn ngữ OCR" hint="Dùng cho trang quét hoặc ảnh.">
            <Select<string>
              value={ocrLanguage}
              onChange={setOcrLanguage}
              options={OCR_LANG_OPTIONS}
            />
          </OptionRow>

          <OptionRow label="Định dạng được hỗ trợ">
            <ul className="space-y-0.5 font-mono text-[11.5px] text-ink-soft">
              <li>
                📄 <span className="text-ink">.pdf</span> — born-digital + bản quét
              </li>
              <li>
                🖼️ <span className="text-ink">.png .jpg .tiff .bmp .webp</span>
              </li>
            </ul>
          </OptionRow>

          <OptionRow label="API">
            <code className="block bg-bg-soft px-2 py-1 font-mono text-[11px]">
              POST /api/tools/convert/file
            </code>
          </OptionRow>

          <OptionRow label="Tự động">
            <p className="text-[11.5px] leading-snug text-ink-soft">
              Có lớp văn bản → trích trực tiếp (nhanh).
              <br />
              Bản quét → tự động OCR qua Tesseract.
              <br />
              PDF lai → chọn theo từng trang.
            </p>
          </OptionRow>
        </>
      }
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-ink-mute">
            {job
              ? `${job.status} · ${Math.round(job.progress * 100)}%`
              : !file
                ? "Chọn tệp .pdf hoặc ảnh, sau đó bấm Chuyển"
                : "Sẵn sàng — bấm Chuyển để xếp hàng đợi"}
          </span>
          <Button variant="primary" size="md" onClick={onRun} disabled={!canRun}>
            {startJob.isPending ? <Spinner /> : <Play size={14} />}
            Chuyển
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
          if (dropped && fileExtIsSupported(dropped.name)) {
            setFile(dropped);
          } else if (dropped) {
            toast.error(`Định dạng không hỗ trợ: ${dropped.name}`);
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_ATTR}
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
                <FileType size={16} className="shrink-0 text-accent" />
              )}
              <span className="truncate font-mono">
                {file ? file.name : "Chưa chọn tệp PDF hoặc ảnh"}
              </span>
            </div>
            {file && (
              <p className="mt-1 font-mono text-[11px] text-ink-mute">
                {fileSizeNote} · sẵn sàng chuyển
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
            {file ? "Đổi tệp" : "Chọn tệp"}
          </Button>
        </div>
      </div>

      <p className="text-[11.5px] leading-snug text-ink-soft">
        Dữ liệu xử lý hoàn toàn cục bộ qua Tesseract — không gửi tệp ra ngoài.
        <br />
        Sau khi có <code className="font-mono">.docx</code>, bạn có thể{" "}
        <a className="font-mono text-accent underline" href="#">
          chuyển sang Dịch thuật
        </a>{" "}
        để dịch sang ngôn ngữ khác.
      </p>

      {errMsg && (
        <div className="flex items-start gap-2 border border-danger bg-paper px-3 py-2 text-sm text-danger">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{errMsg}</span>
        </div>
      )}

      {job ? (
        <div className="space-y-2">
          <h3 className="font-mono text-[11px] uppercase tracking-wide text-ink-soft">
            Tác vụ hiện tại
          </h3>
          <JobCard job={job} />
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
            Chọn một tệp <span className="mx-1 font-mono text-ink">.pdf</span> hoặc ảnh, rồi bấm
            Chuyển. Tác vụ chạy nền — tiến độ hiển thị ngay tại đây.
          </EmptyHint>
        )
      )}
    </ToolShell>
  );
}
