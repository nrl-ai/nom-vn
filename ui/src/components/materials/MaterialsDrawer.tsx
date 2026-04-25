import { useRef, useState } from "react";
import { Upload, Loader2, AlertCircle, FileText, CheckCircle2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useIndexSpace, useMaterials, useUploadMaterial } from "@/api/queries";
import { cn, formatBytes } from "@/lib/utils";
import { ACCEPT_EXTENSIONS, getFileTypeMeta } from "@/lib/fileTypes";
import { MaterialViewer } from "./MaterialViewer";
import type { Material } from "@/api/types";

interface Props {
  spaceId: string | null;
}

interface UploadJob {
  id: string;
  name: string;
  size: number;
  status: "pending" | "ok" | "error";
  error?: string;
}

export function MaterialsDrawer({ spaceId }: Props) {
  const matsQ = useMaterials(spaceId);
  const upload = useUploadMaterial(spaceId);
  const indexSpace = useIndexSpace(spaceId);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  const [openMaterial, setOpenMaterial] = useState<Material | null>(null);

  const onUploadFiles = async (files: FileList | null) => {
    if (!files || files.length === 0 || !spaceId) return;
    // Snapshot the queue up front so we can render per-file progress.
    const newJobs: UploadJob[] = Array.from(files).map((f) => ({
      id: crypto.randomUUID(),
      name: f.name,
      size: f.size,
      status: "pending",
    }));
    setJobs((prev) => [...prev, ...newJobs]);
    for (let i = 0; i < files.length; i++) {
      const f = files[i]!;
      const job = newJobs[i]!;
      try {
        await upload.mutateAsync(f);
        setJobs((prev) => prev.map((j) => (j.id === job.id ? { ...j, status: "ok" } : j)));
      } catch (err) {
        setJobs((prev) =>
          prev.map((j) =>
            j.id === job.id ? { ...j, status: "error", error: (err as Error).message } : j,
          ),
        );
      }
    }
    // Auto-clear "ok" rows after a beat so the list doesn't pile up.
    setTimeout(() => {
      setJobs((prev) => prev.filter((j) => j.status !== "ok"));
    }, 2500);
    // Now eagerly process whatever just landed. Lazy indexing on first
    // ask was the previous design; users found "pending index" stuck
    // there confusing. This call is synchronous on the server and can
    // take seconds for OCR / DOCX / large PDF — the indexing-state
    // banner below covers it.
    try {
      await indexSpace.mutateAsync();
    } catch {
      // mutation surfaces error in the banner
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (!spaceId) return;
    onUploadFiles(e.dataTransfer.files);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 px-4 pb-2 pt-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="section-mark">§ sources</h2>
          {matsQ.data && matsQ.data.length > 0 && (
            <span className="font-mono text-[10px] text-ink-mute">{matsQ.data.length}</span>
          )}
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (spaceId) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={cn(
            "cursor-pointer border-2 border-dashed p-4 text-center transition-colors",
            !spaceId
              ? "cursor-not-allowed border-line opacity-40"
              : dragOver
                ? "border-accent bg-accent/5"
                : "border-line hover:border-ink hover:bg-bg-soft",
          )}
          onClick={() => spaceId && fileRef.current?.click()}
        >
          <input
            ref={fileRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => onUploadFiles(e.target.files)}
            accept={ACCEPT_EXTENSIONS}
          />
          <Upload
            size={20}
            className={cn("mx-auto mb-2", dragOver ? "text-accent" : "text-ink-mute")}
          />
          <div className="text-xs text-ink-soft">
            {!spaceId
              ? "Select a space first"
              : dragOver
                ? "Drop to upload"
                : "Drag & drop or click to upload"}
          </div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-ink-mute">
            pdf · text · image (ocr) · code
          </div>
        </div>

        {indexSpace.isPending && (
          <div className="mt-2 flex animate-fade-in items-center gap-2 border border-line-soft bg-bg-soft px-2.5 py-1.5 text-[11px] text-ink-soft">
            <Loader2 size={11} className="shrink-0 animate-spin text-accent" />
            <span>Indexing — parse, chunk, embed…</span>
          </div>
        )}
        {indexSpace.isError && (
          <div className="mt-2 flex animate-fade-in items-start gap-2 border border-danger/60 bg-paper px-2.5 py-1.5 text-[11px] text-danger">
            <AlertCircle size={11} className="mt-0.5 shrink-0" />
            <span className="break-words">
              Indexing failed: {(indexSpace.error as Error).message}
            </span>
          </div>
        )}
        {jobs.length > 0 && (
          <ul className="mt-2 space-y-1">
            {jobs.map((j) => (
              <li
                key={j.id}
                className={cn(
                  "flex animate-fade-in items-center gap-2 border px-2.5 py-1.5 text-[11px]",
                  j.status === "pending"
                    ? "border-line-soft bg-bg-soft text-ink-soft"
                    : j.status === "ok"
                      ? "border-ok/40 bg-paper text-ok"
                      : "border-danger/60 bg-paper text-danger",
                )}
              >
                {j.status === "pending" && (
                  <Loader2 size={11} className="shrink-0 animate-spin text-accent" />
                )}
                {j.status === "ok" && <CheckCircle2 size={11} className="shrink-0" />}
                {j.status === "error" && <AlertCircle size={11} className="shrink-0" />}
                <span className="vn-text flex-1 truncate">{j.name}</span>
                <span className="shrink-0 font-mono text-[9.5px] opacity-70">
                  {formatBytes(j.size)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="px-2 pb-4">
          {!spaceId && (
            <div className="px-3 py-6 text-center text-xs italic text-ink-mute">
              No space selected.
            </div>
          )}
          {spaceId && matsQ.isLoading && (
            <div className="px-3 py-3 text-xs italic text-ink-mute">Loading…</div>
          )}
          {spaceId && matsQ.data && matsQ.data.length === 0 && jobs.length === 0 && (
            <div className="px-3 py-6 text-center">
              <FileText size={20} className="mx-auto mb-2 text-ink-mute" />
              <p className="text-xs italic text-ink-mute">No sources yet. Upload above.</p>
            </div>
          )}
          {matsQ.data?.map((m) => (
            <MaterialItem key={m.id} material={m} onOpen={() => setOpenMaterial(m)} />
          ))}
        </div>
        <MaterialViewer
          spaceId={spaceId}
          material={openMaterial}
          onClose={() => setOpenMaterial(null)}
        />

        {/* Studio placeholder section — NotebookLM has Audio Overview /
            Mind Map / FAQ here. We don't yet; be honest. */}
        <div className="mt-2 border-t border-line-soft px-4 pb-6 pt-4">
          <h2 className="section-mark mb-3">§ studio</h2>
          <div className="space-y-1.5">
            {["Briefing doc", "Mind map", "FAQ", "Audio overview"].map((label) => (
              <div
                key={label}
                className="flex items-center justify-between border border-line-soft bg-paper px-3 py-2 text-xs text-ink-mute"
              >
                <span>{label}</span>
                <span className="font-mono text-[9.5px] uppercase tracking-widest opacity-60">
                  v0.3
                </span>
              </div>
            ))}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}

function MaterialItem({ material, onOpen }: { material: Material; onOpen: () => void }) {
  const meta = getFileTypeMeta(material.name);
  const Icon = meta.icon;
  const indexed = material.n_chunks > 0;

  const row = (
    <button
      onClick={onOpen}
      className="mb-1 w-full border border-line-soft bg-paper px-3 py-2 text-left transition-all hover:border-ink hover:shadow-editorial-soft"
      title="View original + extracted text"
    >
      <div className="flex items-start gap-2">
        <Icon size={14} className={cn("mt-0.5 shrink-0", meta.colorClass)} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-1.5">
            <span className="vn-text truncate text-xs font-medium text-ink">{material.name}</span>
            <span className="shrink-0 font-mono text-[9px] uppercase tracking-widest text-ink-mute opacity-70">
              {meta.label}
            </span>
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-[10px] text-ink-mute">
            <span>{formatBytes(material.n_bytes)}</span>
            <span className="opacity-50">·</span>
            <span className={cn(indexed ? "text-ok" : "text-ink-mute")}>
              {indexed ? `${material.n_chunks} chunks` : "pending index"}
            </span>
          </div>
        </div>
      </div>
    </button>
  );

  if (!meta.hint) return row;
  return (
    <Tooltip delayDuration={500}>
      <TooltipTrigger asChild>{row}</TooltipTrigger>
      <TooltipContent side="left">{meta.hint}</TooltipContent>
    </Tooltip>
  );
}
