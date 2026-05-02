import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Download,
  HardDrive,
  Loader2,
  Package,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ToolShell, Panel, EmptyHint } from "../ToolShell";
import {
  useCancelPull,
  useDeleteModel,
  useModelPulls,
  useModelsList,
  useStartPull,
  useStartPullBatch,
} from "@/api/queries";
import type { CuratedModel, OllamaModelInfo, PullState } from "@/api/types";

const TIER_LABEL: Record<CuratedModel["tier"], string> = {
  light: "Nhẹ",
  standard: "Tiêu chuẩn",
  power: "Mạnh",
};

const TIER_COLOR: Record<CuratedModel["tier"], string> = {
  light: "text-ink",
  standard: "text-accent",
  power: "text-ink",
};

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "—";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatGB(gb: number): string {
  if (gb < 1) return `${(gb * 1024).toFixed(0)} MB`;
  return `${gb.toFixed(1)} GB`;
}

export function ModelsPage() {
  const modelsQ = useModelsList();
  const pullsQ = useModelPulls();
  const startPull = useStartPull();
  const startBatch = useStartPullBatch();
  const cancelPull = useCancelPull();
  const deleteModel = useDeleteModel();

  const [selected, setSelected] = useState<Set<string>>(new Set());

  const data = modelsQ.data;
  const pulls = pullsQ.data?.pulls ?? [];
  const activePulls = pulls.filter(
    (p) => p.status === "pending" || p.status === "downloading",
  );

  const installed = useMemo<Set<string>>(
    () => new Set((data?.ollama.models ?? []).map((m) => m.name)),
    [data?.ollama.models],
  );

  const toggleSelected = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onPullSelected = () => {
    const wanted = [...selected].filter((id) => !installed.has(id));
    if (wanted.length === 0) {
      toast.info("Đã chọn nhưng tất cả đều có sẵn — không cần tải lại.");
      return;
    }
    startBatch.mutate(wanted, {
      onSuccess: ({ results }) => {
        const started = results.filter((r) => r.status === "started").length;
        const rejected = results.filter((r) => r.status === "rejected");
        if (started > 0) {
          toast.success(`Đã bắt đầu ${started} mô hình. Theo dõi ở phần "Đang tải".`);
        }
        if (rejected.length > 0) {
          toast.warning(
            `${rejected.length} mô hình bị hoãn: ${rejected.map((r) => r.error).join("; ")}`,
          );
        }
        setSelected(new Set());
      },
    });
  };

  const onPullSingle = (id: string) => {
    startPull.mutate(id, {
      onSuccess: () => toast.success(`Đã bắt đầu tải ${id}.`),
    });
  };

  const onCancel = (pullId: string, model: string) => {
    cancelPull.mutate(pullId, {
      onSuccess: () => toast.info(`Đã huỷ ${model}.`),
    });
  };

  const onDelete = (name: string) => {
    if (!window.confirm(`Xoá mô hình ${name}? Có thể tải lại sau.`)) return;
    deleteModel.mutate(name, {
      onSuccess: () => toast.success(`Đã xoá ${name}.`),
    });
  };

  const ollamaUnreachable = data && !data.ollama.reachable;
  const totalSize = (data?.ollama.models ?? []).reduce((s, m) => s + m.size_bytes, 0);

  return (
    <ToolShell
      icon={Package}
      title="Mô hình"
      subtitle="quản lý mô hình AI cài đặt cục bộ"
      pending={startPull.isPending || startBatch.isPending}
      options={
        <>
          <div className="space-y-2 text-[12px] text-ink-soft">
            <div className="flex items-center gap-2">
              <HardDrive size={13} className="shrink-0 text-accent" />
              <span>
                {data?.ollama.models.length ?? 0} mô hình ·{" "}
                <span className="text-ink">{formatBytes(totalSize)}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Cpu size={13} className="shrink-0 text-accent" />
              <span>
                Ollama:{" "}
                {data?.ollama.reachable ? (
                  <span className="text-ink">đang chạy</span>
                ) : (
                  <span className="text-danger">không kết nối được</span>
                )}
              </span>
            </div>
            {data && data.hf_cache.length > 0 && (
              <div className="flex items-center gap-2">
                <Package size={13} className="shrink-0 text-accent" />
                <span>
                  Cache HF: {data.hf_cache.length} kho ·{" "}
                  {formatBytes(data.hf_cache.reduce((s, h) => s + h.size_bytes, 0))}
                </span>
              </div>
            )}
          </div>
          {selected.size > 0 && (
            <div className="mt-4 border-l-2 border-accent bg-paper p-3">
              <p className="font-mono text-[11px] uppercase tracking-widest text-ink-mute">
                Đã chọn
              </p>
              <p className="mt-1 text-sm text-ink">
                <strong>{selected.size}</strong> mô hình
              </p>
              <Button
                variant="primary"
                size="sm"
                className="mt-2 w-full"
                onClick={onPullSelected}
                disabled={startBatch.isPending}
              >
                <Download size={13} />
                Tải tất cả
              </Button>
            </div>
          )}
        </>
      }
    >
      {ollamaUnreachable && (
        <div className="flex items-start gap-2 border-l-2 border-danger bg-paper px-3 py-2 text-sm text-ink">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-danger" />
          <div>
            <strong>Không kết nối được Ollama</strong> tại{" "}
            <code className="font-mono text-[12px]">{data.ollama.url}</code>. Hãy chắc chắn rằng{" "}
            <code className="font-mono">ollama serve</code> đang chạy. Danh sách dưới đây sẽ
            trống cho đến khi kết nối lại.
          </div>
        </div>
      )}

      {/* Active pulls — sticky at the top so the user always sees progress */}
      {activePulls.length > 0 && (
        <Panel label="Đang tải" hint={`${activePulls.length} mô hình`}>
          <ul className="space-y-2">
            {activePulls.map((p) => (
              <PullProgressRow
                key={p.pull_id}
                pull={p}
                onCancel={() => onCancel(p.pull_id, p.model)}
              />
            ))}
          </ul>
        </Panel>
      )}

      {/* Recently completed pulls */}
      {pulls.some((p) => p.status === "success" || p.status === "error" || p.status === "cancelled") && (
        <Panel
          label="Gần đây"
          hint="lịch sử tải gần đây — tự xoá sau 10 phút"
        >
          <ul className="space-y-1">
            {pulls
              .filter((p) => p.status !== "pending" && p.status !== "downloading")
              .map((p) => (
                <li
                  key={p.pull_id}
                  className="flex items-center gap-2 border-l-2 border-line pl-3 font-mono text-[12px] text-ink-soft"
                >
                  {p.status === "success" ? (
                    <CheckCircle2 size={12} className="text-accent" />
                  ) : (
                    <X size={12} className="text-danger" />
                  )}
                  <span className="text-ink">{p.model}</span>
                  <span>{p.status === "success" ? "thành công" : p.error || p.status}</span>
                </li>
              ))}
          </ul>
        </Panel>
      )}

      {/* Curated catalog with checkboxes for multi-select */}
      <Panel
        label="Đề xuất cho tiếng Việt"
        hint="chọn nhiều mô hình rồi bấm 'Tải tất cả' để tải song song"
      >
        <ul className="space-y-1.5">
          {(data?.catalog ?? []).map((m) => (
            <CatalogRow
              key={m.id}
              model={m}
              installed={installed.has(m.id)}
              checked={selected.has(m.id)}
              onToggle={() => toggleSelected(m.id)}
              onPull={() => onPullSingle(m.id)}
            />
          ))}
        </ul>
      </Panel>

      {/* Installed models */}
      <Panel
        label="Đã cài đặt"
        hint={`${data?.ollama.models.length ?? 0} mô hình`}
      >
        {data?.ollama.models.length === 0 ? (
          <EmptyHint>
            Chưa có mô hình nào. Chọn từ danh sách <em>Đề xuất</em> ở trên rồi bấm Tải.
          </EmptyHint>
        ) : (
          <ul className="space-y-1">
            {(data?.ollama.models ?? []).map((m) => (
              <InstalledRow key={m.name} model={m} onDelete={() => onDelete(m.name)} />
            ))}
          </ul>
        )}
      </Panel>

      {/* HF cache (read-only — can't easily uninstall a partial revision) */}
      {data && data.hf_cache.length > 0 && (
        <Panel
          label="Cache HuggingFace"
          hint="trọng số đã tải — quản lý qua `huggingface-cli delete-cache`"
        >
          <ul className="space-y-1 font-mono text-[12px] text-ink-soft">
            {data.hf_cache.map((h) => (
              <li key={h.repo_id} className="flex items-center justify-between gap-2">
                <span className="truncate text-ink">{h.repo_id}</span>
                <span>{formatBytes(h.size_bytes)}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </ToolShell>
  );
}

function CatalogRow({
  model,
  installed,
  checked,
  onToggle,
  onPull,
}: {
  model: CuratedModel;
  installed: boolean;
  checked: boolean;
  onToggle: () => void;
  onPull: () => void;
}) {
  return (
    <li
      className={cn(
        "flex items-center gap-3 border-l-2 bg-paper px-3 py-2",
        installed ? "border-accent" : checked ? "border-ink" : "border-line",
      )}
    >
      {!installed && (
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="h-4 w-4 shrink-0 cursor-pointer accent-accent"
          aria-label={`Chọn ${model.label}`}
        />
      )}
      {installed && <CheckCircle2 size={16} className="shrink-0 text-accent" />}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-sm text-ink">{model.label}</span>
          <span className={cn("text-[10px] uppercase tracking-widest", TIER_COLOR[model.tier])}>
            {TIER_LABEL[model.tier]}
          </span>
        </div>
        <p className="mt-0.5 font-mono text-[11px] text-ink-soft">
          {formatGB(model.size_gb)} · cần {model.needs_ram_gb} GB RAM · {model.license}
        </p>
      </div>
      {!installed && (
        <Button variant="outline" size="sm" onClick={onPull}>
          <Download size={12} />
          Tải
        </Button>
      )}
    </li>
  );
}

function InstalledRow({
  model,
  onDelete,
}: {
  model: OllamaModelInfo;
  onDelete: () => void;
}) {
  return (
    <li className="flex items-center justify-between gap-3 border-l-2 border-accent bg-paper px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <CheckCircle2 size={14} className="shrink-0 text-accent" />
          <span className="truncate font-mono text-sm text-ink">{model.name}</span>
        </div>
        <p className="mt-0.5 font-mono text-[11px] text-ink-soft">
          {formatBytes(model.size_bytes)}
          {model.modified_at ? ` · cập nhật ${new Date(model.modified_at).toLocaleDateString()}` : ""}
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={onDelete}>
        <Trash2 size={12} />
        Xoá
      </Button>
    </li>
  );
}

function PullProgressRow({
  pull,
  onCancel,
}: {
  pull: PullState;
  onCancel: () => void;
}) {
  const pct = Math.round(pull.progress * 100);
  return (
    <li className="border-l-2 border-accent bg-paper px-3 py-2">
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <Loader2 size={13} className="shrink-0 animate-spin text-accent" />
          <span className="font-mono text-sm text-ink">{pull.model}</span>
        </div>
        <Button variant="outline" size="sm" onClick={onCancel}>
          <X size={12} />
          Huỷ
        </Button>
      </div>
      <div className="mt-1.5 h-1.5 w-full overflow-hidden bg-bg-soft">
        <div
          className="h-full bg-accent transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1 font-mono text-[11px] text-ink-soft">
        {pct}% · {formatBytes(pull.downloaded_bytes)} / {formatBytes(pull.total_bytes)}
      </p>
    </li>
  );
}
