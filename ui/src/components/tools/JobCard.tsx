import { CheckCircle2, Download, Loader2, X, AlertTriangle, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCancelJob, useDeleteJob } from "@/api/queries";
import { api } from "@/api/client";
import type { BgJob } from "@/api/types";

// Inline-renders one background job — status badge, progress bar,
// download / cancel buttons. Used by TranslatePage, ConvertPage, and
// the JobsPage queue view so the UX is identical across all three.

function fmtKind(kind: string): string {
  if (kind === "translate-file") return "Dịch tệp";
  if (kind === "convert-file") return "Chuyển định dạng";
  return kind;
}

function fmtAge(ts: number): string {
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (sec < 60) return `${sec} s`;
  if (sec < 3600) return `${Math.floor(sec / 60)} ph`;
  return `${Math.floor(sec / 3600)} g`;
}

/** Estimate seconds remaining from elapsed * (1 - progress) / progress.
 *  Returns null when the estimate isn't useful yet (no progress, just
 *  started, or close to done). */
function fmtEta(job: BgJob): string | null {
  if (job.status !== "running" || job.progress <= 0.01 || job.progress >= 0.99) return null;
  const elapsed = Math.max(0.5, Date.now() / 1000 - job.created_at);
  const remainingSec = (elapsed * (1 - job.progress)) / job.progress;
  if (remainingSec < 1) return null;
  if (remainingSec < 60) return `~${Math.ceil(remainingSec)} s`;
  return `~${Math.ceil(remainingSec / 60)} ph`;
}

function StatusBadge({ status }: { status: BgJob["status"] }): React.ReactElement {
  const map: Record<BgJob["status"], { label: string; cls: string; icon: React.ReactElement }> = {
    queued: {
      label: "đang chờ",
      cls: "border-ink-mute text-ink-soft",
      icon: <Clock size={11} />,
    },
    running: {
      label: "đang chạy",
      cls: "border-accent text-accent",
      icon: <Loader2 size={11} className="animate-spin" />,
    },
    completed: {
      label: "hoàn tất",
      cls: "border-emerald-700 text-emerald-700",
      icon: <CheckCircle2 size={11} />,
    },
    failed: {
      label: "lỗi",
      cls: "border-danger text-danger",
      icon: <AlertTriangle size={11} />,
    },
    cancelled: {
      label: "đã huỷ",
      cls: "border-ink-mute text-ink-mute",
      icon: <X size={11} />,
    },
  };
  const { label, cls, icon } = map[status];
  return (
    <span
      className={`inline-flex items-center gap-1 border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${cls}`}
    >
      {icon}
      {label}
    </span>
  );
}

function ProgressBar({
  value,
  status,
}: {
  value: number;
  status: BgJob["status"];
}): React.ReactElement {
  const pct = Math.max(0, Math.min(100, value * 100));
  const indeterminate = status === "queued" || (status === "running" && value === 0);
  const barCls =
    status === "completed"
      ? "bg-emerald-600"
      : status === "failed"
        ? "bg-danger"
        : status === "cancelled"
          ? "bg-ink-mute"
          : "bg-accent";
  return (
    <div className="relative h-1.5 w-full overflow-hidden bg-bg-soft">
      {indeterminate ? (
        <div className={`absolute inset-y-0 w-1/3 animate-pulse ${barCls}`} />
      ) : (
        <div
          className={`absolute inset-y-0 left-0 transition-[width] duration-300 ${barCls}`}
          style={{ width: `${pct}%` }}
        />
      )}
    </div>
  );
}

interface JobCardProps {
  job: BgJob;
  /** Compact mode for the sidebar / queue list — hides the long source filename row. */
  compact?: boolean;
}

export function JobCard({ job, compact = false }: JobCardProps): React.ReactElement {
  const cancelM = useCancelJob();
  const deleteM = useDeleteJob();

  const meta = job.result_meta ?? {};
  const inputName = (meta.input_filename as string | undefined) ?? "—";
  const isTranslate = job.kind === "translate-file";
  const target = (meta.target as string | undefined) ?? "";
  const source = (meta.source as string | undefined) ?? "";
  const directionLabel = isTranslate && source && target ? `${source} → ${target}` : null;

  const onDownload = (): void => {
    if (!job.download_url) return;
    const a = document.createElement("a");
    a.href = api.jobs.downloadUrl(job.id);
    a.download = job.result_filename ?? "download";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const isInFlight = job.status === "queued" || job.status === "running";
  const pct = Math.round(job.progress * 100);
  const eta = fmtEta(job);

  return (
    <div className="border border-ink/15 bg-paper px-3 py-2.5 text-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <StatusBadge status={job.status} />
          <span className="font-mono text-[12px] text-ink">{fmtKind(job.kind)}</span>
          {directionLabel && (
            <span className="font-mono text-[11px] text-ink-mute">{directionLabel}</span>
          )}
        </div>
        <span
          className="font-mono text-[10.5px] text-ink-mute"
          title={`updated ${fmtAge(job.updated_at)} ago`}
        >
          {pct}% · {fmtAge(job.created_at)}
          {eta && ` · còn ${eta}`}
        </span>
      </div>
      {!compact && (
        <p className="mt-1 truncate font-mono text-[11px] text-ink-soft" title={inputName}>
          {inputName}
        </p>
      )}
      <div className="mt-2">
        <ProgressBar value={job.progress} status={job.status} />
      </div>
      {job.error && <p className="mt-1 break-words text-[11.5px] text-danger">{job.error}</p>}
      <div className="mt-2 flex items-center justify-end gap-1.5">
        {isInFlight && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => cancelM.mutate(job.id)}
            disabled={cancelM.isPending}
          >
            <X size={12} />
            Huỷ
          </Button>
        )}
        {job.status === "completed" && job.download_url && (
          <Button variant="primary" size="sm" onClick={onDownload}>
            <Download size={12} />
            Tải về
          </Button>
        )}
        {!isInFlight && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => deleteM.mutate(job.id)}
            disabled={deleteM.isPending}
            title="Xoá khỏi danh sách"
          >
            Xoá
          </Button>
        )}
      </div>
    </div>
  );
}
